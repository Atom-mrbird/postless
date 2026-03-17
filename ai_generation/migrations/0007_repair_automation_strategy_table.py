from django.db import migrations, models
import uuid

def ensure_table_exists(apps, schema_editor):
    from django.db import connection
    table_name = 'ai_generation_automationstrategy'
    if table_name not in connection.introspection.table_names():
        with connection.schema_editor() as editor:
            editor.create_model(apps.get_model('ai_generation', 'AutomationStrategy'))

class Migration(migrations.Migration):

    dependencies = [
        ('ai_generation', '0006_automationstrategy_updated_at'),
    ]

    operations = [
        migrations.RunPython(ensure_table_exists, reverse_code=migrations.RunPython.noop),
    ]
