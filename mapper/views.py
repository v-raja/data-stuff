# Create your views here.
import json
import os
import uuid

import pandas as pd
import pandera
from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse

from .forms import ApplyTransformationForm, CreateSchemaForm, EditSchemaForm, UploadFileForm
from .helpers import apply_transformations_to_df, execute_mapping_plan, generate_description_dict, \
    generate_pandera_schema, inital_data_mapping_plan, \
    run_data_quality_checks
from .models import Schema, UploadedFile


def upload_files(request, schema_id):
    schema = Schema.objects.get(id=schema_id)
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = form.save()

            # Call python function to generate dictionary
            files = [file.file.path for file in uploaded_files]
            request.session['mapping_plan'] = inital_data_mapping_plan(files, schema.description_dict, json.loads(schema.categories))
            request.session['uploaded_file_ids'] = [file.id for file in uploaded_files]
            return redirect('mapping_correction', schema_id=schema_id)
            # context = {'form': form, 'file_dict': your_python_function(uploaded_files), 'uploaded_files': uploaded_files}
            # Check if it's an HTMX request
            # if 'HTTP_HX_REQUEST' in request.META:
            #     html = render_to_string('mapper/mapping_correction.html', context, request=request)
            #     return HttpResponse(html)
            # else:
            # return render(request, 'mapper/mapping_correction.html', context)
    else:
        form = UploadFileForm()
    return render(request, 'mapper/upload_files.html', {'form': form, 'schema_id': schema_id, 'schema': schema})


def mapping_correction_form(request, schema_id):
    if request.method == 'POST':
        if 'next' in request.POST:
            return HttpResponseRedirect(reverse('apply_transformations', args=(schema_id,)))
    mapping_plan = request.session.get('mapping_plan', {})
    uploaded_file_ids = request.session.get('uploaded_file_ids', [])
    schema = Schema.objects.get(id=schema_id)
    return render(request, 'mapper/mapping_correction.html', {'mapping_plan': mapping_plan, 'uploaded_file_ids': uploaded_file_ids, 'schema_id': schema_id, 'schema': schema})


def generate_file(request, schema_id):
    if request.method == 'POST':
        # Extract mapping corrections from POST data
        mapping_corrections = dict(request.POST)

        # Remove the CSRF token from the mapping corrections
        mapping_corrections.pop('csrfmiddlewaretoken', None)

        # For simplicity, we are just going to concatenate all files.
        # This logic should be replaced with the actual logic for generating the final output file based on the mapping corrections.
        uploaded_file_ids = request.session.get('uploaded_file_ids', [])

        # Get the uploaded files corresponding to the IDs
        uploaded_files = UploadedFile.objects.filter(id__in=uploaded_file_ids)
        files = [file.file.path for file in uploaded_files]
        schema = Schema.objects.get(id=schema_id)
        df = execute_mapping_plan(files, mapping_corrections, schema.description_dict, json.loads(schema.categories))

        # Save the DataFrame as a CSV file
        output_file_path = f'{settings.MEDIA_ROOT}/after_mapping/{uuid.uuid4().hex}.csv'  # generate a unique filename
        df.to_csv(output_file_path)

        # Store the output file path and columns in the session
        request.session['df_path'] = output_file_path
        request.session['columns'] = df.columns.tolist()

        df_json = df.reset_index().to_json(orient="records")
        df_data = json.loads(df_json)
        df_header = df.columns.values.tolist()

        # Convert the DataFrame to HTML
        # df_html = df.to_html()

        # Return the DataFrame HTML
        return HttpResponse(render_to_string("mapper/dataframe.html", {"df_data": df_data, "df_header": df_header}))

    else:
        return HttpResponseNotAllowed(['POST'])

# def data_quality(request, schema_id):
#     if request.method == 'GET':
#         columns = request.session['columns']
#         after_mapping_df_path = request.session['dataframe_file']
#         schema = Schema.objects.get(id=schema_id)
#         errors = run_data_quality_checks(after_mapping_df_path, schema.pandera_schema)  # Assuming this function runs the data quality checks and returns a dict with column names and corresponding errors
#
#         form = ApplyTransformationForm(columns=columns, errors=errors)
#         return render(request, 'mapper/data_quality.html', {'form': form, 'schema_id': schema_id})
#     else:
#         return HttpResponseNotAllowed(['GET'])

# def apply_transformations(request, schema_id):
#     if request.method == 'POST':
#         # Save DataFrame to file and return as response
#         if 'download' in request.POST:
#             filepath = request.session['dataframe_file']
#             response = FileResponse(open(filepath, 'rb'), content_type='application/vnd.ms-excel')
#             response['Content-Disposition'] = 'attachment; filename=data.csv'
#             return response
#
#         # Apply transformations to DataFrame
#         form = ApplyTransformationForm(request.POST)
#         if form.is_valid():
#             transformations = {key.replace('transformation_', ''): value for key, value in form.cleaned_data.items()}
#             df_path = request.session['dataframe_file']
#             df = pd.read_csv(df_path)
#             transformed_df = apply_transformations_to_df(df, transformations)
#             schema = Schema.objects.get(id=schema_id)
#             errors = run_data_quality_checks(transformed_df, schema.pandera_schema)
#
#             transformed_df.to_csv(request.session['dataframe_file'], index=False)
#
#             # If there are still errors, re-render the form with the new errors
#             if errors:
#                 form = ApplyTransformationForm(columns=transformations.keys(), initial=transformations, errors=errors)
#
#             # Render the form with the transformed DataFrame
#             return render(request, 'mapper/apply_transformations.html', {'form': form, 'schema_id': schema_id, 'dataframe_html': transformed_df.to_html()})
#
#         else:
#             # Form is not valid, show the form with error messages
#             return render(request, 'mapper/apply_transformations.html', {'form': form, 'schema_id': schema_id})
#
#     else:
#         # Form is not submitted, show the initial form
#         df = pd.read_csv(request.session['dataframe_file'])
#         schema = Schema.objects.get(id=schema_id)
#         errors = run_data_quality_checks(df, schema.pandera_schema)
#         form = ApplyTransformationForm(columns=df.columns, errors=errors)
#         return render(request, 'mapper/apply_transformations.html', {'form': form, 'schema_id': schema_id, 'dataframe_html': df.to_html()})

def apply_transformations(request, schema_id):
    # Get the path of the generated file from the session
    df_path = request.session.get('df_path')

    # Load the DataFrame from the CSV file
    df = pd.read_csv(df_path)

    # Get the schema
    schema = Schema.objects.get(id=schema_id)

    # Check the data quality of the DataFrame
    errors = run_data_quality_checks(df, pandera.DataFrameSchema.from_json(schema.pandera_schema))

    # Convert the DataFrame to HTML
    df_json = df.reset_index().to_json(orient="records")
    df_data = json.loads(df_json)
    df_header = df.columns.values.tolist()
    df_html = render_to_string('mapper/dataframe.html', {'df_data': df_data, 'df_header': df_header})

    if request.method == 'POST':
        # Store transformations in initial data
        initial_transformations = {key: value for key, value in request.POST.items() if
                                   key.startswith('transformation_')}
        form = ApplyTransformationForm(request.POST, errors=errors, initial=initial_transformations)
        if form.is_valid():
            # Apply transformations
            transformations = {key.replace('transformation_', ''): value for key, value in form.cleaned_data.items()}
            df = apply_transformations_to_df(df, transformations)

            # Save the DataFrame to the CSV file
            df.to_csv(df_path, index=False)
            df_html = df.to_html()

            # Check if we should download the data
            if 'download' in request.POST:
                # Create a response with the CSV file
                response = FileResponse(open(df_path, 'rb'), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(df_path)}"'
                return response
        else:
            # If form is invalid, show the form with error messages
            df_json = df.reset_index().to_json(orient="records")
            df_data = json.loads(df_json)
            df_header = df.columns.values.tolist()
            df_html = render_to_string('mapper/dataframe.html', {'df_data': df_data, 'df_header': df_header})
            request.session['df_path'] = df_path
            return render(request, 'mapper/apply_transformations.html', {'form': form, 'dataframe_html': df_html})
    else:
        # For GET requests, just display the form
        form = ApplyTransformationForm(errors=errors, columns=df.columns)

    request.session['df_path'] = df_path

    return render(request, 'mapper/apply_transformations.html', {'form': form, 'dataframe_html': df_html})

# def create_schema(request):
#     if request.method == 'POST':
#         form = CreateSchemaForm(request.POST, request.FILES)
#         if form.is_valid():
#             # Load the uploaded dataset into a DataFrame
#             df = pd.read_csv(form.cleaned_data['dataset'])
#
#             # Generate the initial description_dict and pandera_schema
#             description_dict = generate_description_dict(df)
#             pandera_schema = generate_pandera_schema(df)
#
#             # Render the form for editing the schema
#             context = {
#                 'description_dict': description_dict,
#                 'pandera_schema': pandera_schema,
#             }
#             return render(request, 'mapper/edit_schema.html', context)
#     else:
#         form = CreateSchemaForm()
#     return render(request, 'mapper/create_schema.html', {'form': form})
#
def create_schema(request):
    if request.method == 'POST':
        form = CreateSchemaForm(request.POST, request.FILES)
        if form.is_valid():
            # Load the uploaded dataset into a DataFrame
            df = pd.read_csv(form.cleaned_data['example_dataset'])

            # Generate the initial description_dict and pandera_schema
            description_dict, categories_dict = generate_description_dict(df)
            pandera_schema = generate_pandera_schema(df)

            # Initialize the EditSchemaForm with the initial data
            edit_form = EditSchemaForm(initial={'description_dict': description_dict, 'pandera_schema': pandera_schema, 'name': form.cleaned_data['name'], 'categories': json.dumps(categories_dict)})

            # Render the form for editing the schema
            return render(request, 'mapper/edit_schema.html', {'form': edit_form})
    else:
        form = CreateSchemaForm()
    return render(request, 'mapper/create_schema.html', {'form': form})


def save_schema(request):
    if request.method == 'POST':
        # all keys of description_dict are prefixed with 'description_dict_'
        # so we need to remove the prefix and store in a dictionary
        description_dict = {key.replace('description_dict_', ''): value for key, value in request.POST.items() if key.startswith('description_dict_')}
        form = EditSchemaForm(request.POST, description_dict=description_dict)
        if form.is_valid():
            # Save the schema in the database
            form.save()

            # Return a success message
            return redirect('schema_list')
        else:
            # Form is not valid, show the form with error messages
            return render(request, 'mapper/edit_schema.html', {'form': form})

    return HttpResponseNotAllowed(['POST'])

def schema_list(request):
    # Get all the schemas
    schemas = Schema.objects.all()

    # Render the list of schemas
    return render(request, 'mapper/schema_list.html', {'schemas': schemas})
