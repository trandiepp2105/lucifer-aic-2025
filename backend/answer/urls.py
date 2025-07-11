from django.urls import path
from . import views

urlpatterns = [
    # Answer endpoints
    path('api/answers/', views.AnswerListCreateAPIView.as_view(), name='answer-list-create'),
    path('api/answers/<int:answer_id>/', views.AnswerDetailAPIView.as_view(), name='answer-detail'),
    path('api/answers/bulk-delete/', views.AnswerBulkDeleteAPIView.as_view(), name='answer-bulk-delete'),
    
    # TeamAnswer endpoints
    path('api/team-answers/', views.TeamAnswerListCreateAPIView.as_view(), name='team-answer-list-create'),
    path('api/team-answers/delete-all/', views.TeamAnswerBulkDeleteAPIView.as_view(), name='team-answer-bulk-delete'),
    path('api/team-answers/<int:team_answer_id>/', views.TeamAnswerDetailAPIView.as_view(), name='team-answer-detail'),
]

# Available endpoints:
# Answer Management:
# GET /api/answers/ - List all answers (with filtering support by round, query_index, video_name)
# POST /api/answers/ - Create a new answer
# GET /api/answers/{id}/ - Get a specific answer
# PUT /api/answers/{id}/ - Update an answer
# DELETE /api/answers/{id}/ - Delete an answer
# DELETE /api/answers/bulk-delete/ - Bulk delete answers by IDs

# TeamAnswer Management:
# GET /api/team-answers/ - List all team answers (with filtering support by round, query_index, video_name)
# POST /api/team-answers/ - Create a new team answer (temporary answer)
# DELETE /api/team-answers/delete-all/ - Bulk delete team answers (with filtering support)
# GET /api/team-answers/{id}/ - Get a specific team answer
# PUT /api/team-answers/{id}/ - Update a team answer
# DELETE /api/team-answers/{id}/ - Delete a team answer
