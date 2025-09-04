from django.apps import AppConfig


class SpeechConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'speech'
    verbose_name = 'Speech Recognition'
    
    def ready(self):
        """
        Called when the app is ready. This is a good place to perform
        one-time setup like registering signals or starting background services.
        """
        pass
