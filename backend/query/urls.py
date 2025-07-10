from django.urls import path
from . import views

urlpatterns = [
    # Session endpoints
    path('api/sessions/', views.QuerySessionListCreateAPIView.as_view(), name='session-list-create'),
    path('api/sessions/<int:session_id>/', views.QuerySessionDetailAPIView.as_view(), name='session-detail'),
    path('api/sessions/<int:session_id>/queries/', views.QuerySessionQueriesAPIView.as_view(), name='session-queries'),
    
    # Query endpoints
    path('api/queries/', views.QueryListCreateAPIView.as_view(), name='query-list-create'),
    path('api/queries/<int:pk>/', views.QueryDetailAPIView.as_view(), name='query-detail'),
    path('api/queries/bulk-delete/', views.QueryBulkDeleteAPIView.as_view(), name='query-bulk-delete'),
    path('api/queries/<int:pk>/answers/', views.QueryAnswersAPIView.as_view(), name='query-answers'),
    
    # Answer endpoints
    path('api/answers/', views.AnswerListCreateAPIView.as_view(), name='answer-list-create'),
    path('api/answers/<int:answer_id>/', views.AnswerDetailAPIView.as_view(), name='answer-detail'),
    
    # TeamAnswer endpoints
    path('api/team-answers/', views.TeamAnswerListCreateAPIView.as_view(), name='team-answer-list-create'),
    path('api/team-answers/delete-all/', views.TeamAnswerBulkDeleteAPIView.as_view(), name='team-answer-bulk-delete'),
    path('api/team-answers/<int:team_answer_id>/', views.TeamAnswerDetailAPIView.as_view(), name='team-answer-detail'),
]

# Available endpoints:
# Session Management:
# GET /api/sessions/ - List all sessions
# POST /api/sessions/ - Create a new session
# GET /api/sessions/{id}/ - Get a specific session
# DELETE /api/sessions/{id}/ - Delete a session and all its queries
# GET /api/sessions/{id}/queries/ - Get queries in a specific session

# Query Management:
# GET /api/queries/ - List all queries (with filtering support)
# POST /api/queries/ - Create a new query
# GET /api/queries/{id}/ - Get a specific query
# GET /api/queries/{id}/search-frames/ - Search frames for a specific query using its OCR data
# PUT /api/queries/{id}/ - Update a query
# PATCH /api/queries/{id}/ - Partial update a query
# DELETE /api/queries/{id}/ - Delete a query
# DELETE /api/queries/bulk-delete/ - Bulk delete queries
# GET /api/queries/{id}/answers/ - Get answers for a specific query

# Answer Management:
# GET /api/answers/ - List all answers (with filtering support by round, query_index, video_name)
# POST /api/answers/ - Create a new answer
# GET /api/answers/{id}/ - Get a specific answer
# PUT /api/answers/{id}/ - Update an answer
# DELETE /api/answers/{id}/ - Delete an answer

# TeamAnswer Management:
# GET /api/team-answers/ - List all team answers (with filtering support by round, query_index, video_name)
# POST /api/team-answers/ - Create a new team answer (temporary answer)
# DELETE /api/team-answers/delete-all/ - Bulk delete team answers (with filtering support)
# GET /api/team-answers/{id}/ - Get a specific team answer
# PUT /api/team-answers/{id}/ - Update a team answer
# DELETE /api/team-answers/{id}/ - Delete a team answer
