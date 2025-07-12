from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from .models import Query
import os


@receiver(pre_save, sender=Query)
def delete_old_image_on_update(sender, instance, **kwargs):
    """
    Delete old image file when image field is updated
    """
    if not instance.pk:
        return  # New instance, no old file to delete

    try:
        old_instance = Query.objects.get(pk=instance.pk)
        old_image = old_instance.image
        new_image = instance.image
        
        # If image is being changed or removed
        if old_image and old_image != new_image:
            if os.path.isfile(old_image.path):
                os.remove(old_image.path)
                print(f"Deleted old image file: {old_image.path}")
    except Query.DoesNotExist:
        pass  # Old instance doesn't exist
    except Exception as e:
        print(f"Error deleting old image file: {e}")


@receiver(post_delete, sender=Query)
def delete_image_on_query_delete(sender, instance, **kwargs):
    """
    Delete image file when query is deleted
    """
    if instance.image:
        try:
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
                print(f"Deleted image file on query delete: {instance.image.path}")
        except Exception as e:
            print(f"Error deleting image file on query delete: {e}")
