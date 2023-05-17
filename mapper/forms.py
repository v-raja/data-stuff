import json

from django import forms
from jsoneditor.forms import JSONEditor
from multiupload.fields import MultiFileField
from prettyjson import PrettyJSONWidget

from .models import Schema, UploadedFile

class UploadFileForm(forms.Form):
    files = MultiFileField(min_num=1, max_num=5, max_file_size=1024*1024*5)

    def save(self):
        uploaded_files = []
        for each in self.cleaned_data['files']:
            uploaded_file = UploadedFile.objects.create(file=each)
            uploaded_files.append(uploaded_file)
        return uploaded_files


class CreateSchemaForm(forms.Form):
    name = forms.CharField(max_length=128)
    # description = forms.CharField(widget=forms.Textarea, required=False)
    dataset = forms.FileField()

class EditSchemaForm(forms.ModelForm):
    pandera_schema = forms.CharField(widget=forms.Textarea, label='Data Quality Schema')

    class Meta:
        model = Schema
        fields = ['name', 'pandera_schema']

    def __init__(self, *args, **kwargs):
        inital = kwargs.get('initial', {})
        if inital:
            description_dict = inital.pop('description_dict', {})
        else:
            description_dict = kwargs.pop('description_dict', {})
        super().__init__(*args, **kwargs)

        # Group for description fields
        self.description_fields = []

        # Dynamically add a field for each key in the description_dict
        for key, value in description_dict.items():
            field_name = f'description_dict_{key}'
            self.fields[field_name] = forms.CharField(initial=value, label=key)
            self.description_fields.append(field_name)

        # Update the fields attribute of the Meta class to include dynamic fields
        self._meta.fields.extend(self.description_fields)

        if self.initial.get('pandera_schema'):
            # Format the JSON string with indents
            self.initial['pandera_schema'] = json.dumps(json.loads(self.initial['pandera_schema']), indent=4)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Store the form data back into the description_dict JSON field
        instance.description_dict = {key.replace('description_dict_', ''): value for key, value in
                                     self.cleaned_data.items() if key.startswith('description_dict_')}

        # # Get original POST data
        # post_data = self.data
        #
        # # Store the form data back into the description_dict JSON field
        # instance.description_dict = {key.replace('description_dict_', ''): value for key, value in post_data.items() if
        #                              key.startswith('description_dict_')}

        if commit:
            instance.save()
        return instance

    def clean_pandera_schema(self):
        pandera_schema = self.cleaned_data.get('pandera_schema')
        try:
            # Try to parse the pandera schema as JSON
            json.loads(pandera_schema)
        except json.JSONDecodeError:
            raise forms.ValidationError('Invalid JSON format.')
        return pandera_schema