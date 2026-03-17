import os
import shutil

apps = ['users', 'ai_generation']
base_dir = '/'

for app in apps:
    migrations_dir = os.path.join(base_dir, app, 'migrations')
    if os.path.exists(migrations_dir):
        for filename in os.listdir(migrations_dir):
            if filename != '__init__.py' and filename.endswith('.py'):
                filepath = os.path.join(migrations_dir, filename)
                print(f"Removing {filepath}")
                os.remove(filepath)
    else:
        print(f"Directory {migrations_dir} not found.")

print("Migration files cleaned up.")
