from django import forms

from .services import inspect_upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return super().clean(data, initial)
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [super().clean(item, initial) for item in data]


class MultiUploadForm(forms.Form):
    files = MultipleFileField(widget=MultipleFileInput(attrs={"multiple": True}), label="Documentos")

    def clean_files(self):
        files = self.files.getlist("files")
        if not files:
            raise forms.ValidationError("Selecione pelo menos um arquivo.")
        errors = []
        inspected = []
        for uploaded in files:
            try:
                inspected.append(inspect_upload(uploaded))
            except forms.ValidationError as exc:
                errors.append(f"{uploaded.name}: {exc.messages[0]}")
        if errors:
            raise forms.ValidationError(errors)
        return inspected
