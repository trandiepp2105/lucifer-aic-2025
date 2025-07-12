from django.core.management.base import BaseCommand
from answer.sse_service import team_answer_sse_service


class Command(BaseCommand):
    help = 'Test SSE service heartbeat functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing SSE service...'))
        
        try:
            # Test Redis connection
            if team_answer_sse_service.redis_client:
                team_answer_sse_service.redis_client.ping()
                self.stdout.write(self.style.SUCCESS('✓ Redis connection successful'))
                
                # Send test heartbeat
                team_answer_sse_service.send_heartbeat()
                self.stdout.write(self.style.SUCCESS('✓ Heartbeat sent successfully'))
                
                # Test create message
                test_data = {
                    'id': 999,
                    'video_name': 'test_video.mp4',
                    'frame_index': 100,
                    'query_index': 1,
                    'round': 'prelims'
                }
                team_answer_sse_service.publish_team_answer_create(test_data)
                self.stdout.write(self.style.SUCCESS('✓ Test create message sent'))
                
                # Test delete message
                team_answer_sse_service.publish_team_answer_delete([999])
                self.stdout.write(self.style.SUCCESS('✓ Test delete message sent'))
                
                self.stdout.write(self.style.SUCCESS('All SSE tests passed!'))
                
            else:
                self.stdout.write(self.style.ERROR('✗ Redis connection failed'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ SSE test failed: {e}'))
