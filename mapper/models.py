from django.db import models

# Create your models here.

from django.db import models

class UploadedFile(models.Model):
    file = models.FileField(upload_to='uploads/')


class Schema(models.Model):
    name = models.CharField(max_length=128)
    description_dict = models.JSONField()
    pandera_schema = models.JSONField()
    # description = models.TextField(blank=True, null=True)
