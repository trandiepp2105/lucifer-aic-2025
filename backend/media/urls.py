from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
import os
from . import views

urlpatterns = [
    path('api/video/clip/', views.VideoClipAPIView.as_view(), name='video-clip'),
]

# Serve video clips during development and production
if settings.DEBUG or True:  # Always serve video clips
    urlpatterns += static('/media/video_clips/', document_root=os.path.join(settings.MEDIA_ROOT, 'video_clips'))
