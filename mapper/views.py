# Create your views here.
import json

import pandas as pd
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .forms import CreateSchemaForm, EditSchemaForm, UploadFileForm
from .helpers import execute_mapping_plan, generate_description_dict, generate_pandera_schema, inital_data_mapping_plan
from .models import Schema, UploadedFile


def upload_files(request, schema_id):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_files = form.save()
            schema = Schema.objects.get(id=schema_id)
            # Call python function to generate dictionary
            request.session['mapping_plan'] = inital_data_mapping_plan(uploaded_files, schema.description_dict)
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
    return render(request, 'mapper/upload_files.html', {'form': form, 'schema_id': schema_id})


def mapping_correction_form(request, schema_id):
    mapping_plan = request.session.get('mapping_plan', {})
    uploaded_file_ids = request.session.get('uploaded_file_ids', [])
    return render(request, 'mapper/mapping_correction.html', {'mapping_plan': mapping_plan, 'uploaded_file_ids': uploaded_file_ids, 'schema_id': schema_id})


def generate_file(request, schema_id):
    if request.method == 'POST':
        # Extract mapping corrections from POST data
        mapping_corrections = dict(request.POST.lists())

        # Remove the CSRF token from the mapping corrections
        mapping_corrections.pop('csrfmiddlewaretoken', None)

        # For simplicity, we are just going to concatenate all files.
        # This logic should be replaced with the actual logic for generating the final output file based on the mapping corrections.
        uploaded_file_ids = request.session.get('uploaded_file_ids', [])

        # Get the uploaded files corresponding to the IDs
        uploaded_files = UploadedFile.objects.filter(id__in=uploaded_file_ids)
        files = [file.file.path for file in uploaded_files]
        schema = Schema.objects.get(id=schema_id)
        df = execute_mapping_plan(files, mapping_corrections, schema.description_dict)

        # Convert the DataFrame to HTML
        df_html = df.to_html()

        # Return the DataFrame HTML
        return HttpResponse(df_html)

    else:
        return HttpResponseNotAllowed(['POST'])

def data_quality(request, schema_id):
    return None
    # if request.method == 'GET':
    #     form = DataQualityForm(columns=request.session['columns'])
    #     return render(request, 'mapper/data_quality.html', {'form': form})
    # else:
    #     return HttpResponseNotAllowed(['GET'])

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
            df = pd.read_csv(form.cleaned_data['dataset'])

            # Generate the initial description_dict and pandera_schema
            description_dict = generate_description_dict(df)
            pandera_schema = generate_pandera_schema(df)

            # Initialize the EditSchemaForm with the initial data
            edit_form = EditSchemaForm(initial={'description_dict': description_dict, 'pandera_schema': pandera_schema, 'name': form.cleaned_data['name']})

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
