from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("modelos", "0002_fieldregionpreview"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="repeat_layout_per_page",
            field=models.BooleanField(
                default=False,
                help_text="Quando ativo, o catálogo de campos se repete em cada página do documento.",
            ),
        ),
    ]
