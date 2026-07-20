from django.apps import AppConfig

class IssueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'issue'

    def ready(self):
        from . import scheduler
    #need this here to wait the setting up the rest and then import and start the scheduler
        scheduler.start()
