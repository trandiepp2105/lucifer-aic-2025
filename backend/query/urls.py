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
# PUT /api/queries/{id}/ - Update a query
# PATCH /api/queries/{id}/ - Partial update a query
# DELETE /api/queries/{id}/ - Delete a query
# DELETE /api/queries/bulk-delete/ - Bulk delete queries
