from rest_framework import serializers
from .models import Query, Answer, QuerySession, TeamAnswer

class QuerySessionSerializer(serializers.ModelSerializer):
    """Serializer for QuerySession model"""
    queries_count = serializers.SerializerMethodField()
    
    class Meta:
        model = QuerySession
        fields = ['id', 'created_at', 'updated_at', 'queries_count']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_queries_count(self, obj):
        """Get the number of queries in this session"""
        return obj.queries.count()

class QuerySerializer(serializers.ModelSerializer):
    """Serializer for Query model"""
    class Meta:
        model = Query
        fields = [
            'id', 'text', 'ocr', 'speech', 'image', 
            'time', 'background_sound', 'stage', 'session', 
            'created_at', 'updated_at', 
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_image_url(self, obj):
        """Get the full URL for the image"""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    

class AnswerSerializer(serializers.ModelSerializer):
    """Serializer for Answer model"""
    
    class Meta:
        model = Answer
        fields = [
            'id', 'video_name', 'frame_index', 'url', 'qa', 
            'query_index', 'round', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_round(self, value):
        """Validate round field"""
        if value not in ['prelims', 'final']:
            raise serializers.ValidationError("Round must be either 'prelims' or 'final'")
        return value
    
    def validate_frame_index(self, value):
        """Validate frame_index is positive"""
        if value < 0:
            raise serializers.ValidationError("Frame index must be non-negative")
        return value
    
    def validate_query_index(self, value):
        """Validate query_index is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Query index must be non-negative")
        return value

class QueryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Query with file upload"""
    
    class Meta:
        model = Query
        fields = [
            'text', 'ocr', 'speech', 'image', 
            'time', 'background_sound', 'stage', 'session'
        ]
    
    def validate(self, data):
        """Validate that at least one field is provided"""
        if not any([data.get('text'), data.get('ocr'), data.get('speech'), data.get('image')]):
            raise serializers.ValidationError(
                "At least one of text, ocr, speech, or image must be provided"
            )
        return data
    
    def validate_image(self, value):
        """Validate uploaded image"""
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image file too large ( > 10MB )")
            
            # Check file type
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("File is not an image")
        
        return value

class QueryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating Query"""
    
    class Meta:
        model = Query
        fields = [
            'text', 'ocr', 'speech', 'image', 
            'time', 'background_sound', 'stage', 'session'
        ]
    
    def validate_image(self, value):
        """Validate uploaded image"""
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image file too large ( > 10MB )")
            
            # Check file type
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("File is not an image")
        
        return value

class AnswerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Answer"""
    
    class Meta:
        model = Answer
        fields = ['video_name', 'frame_index', 'url', 'qa', 'query_index', 'round']
    
    def validate_round(self, value):
        """Validate round field"""
        if value not in ['prelims', 'final']:
            raise serializers.ValidationError("Round must be either 'prelims' or 'final'")
        return value
    
    def validate_frame_index(self, value):
        """Validate frame_index is positive"""
        if value < 0:
            raise serializers.ValidationError("Frame index must be non-negative")
        return value
    
    def validate_query_index(self, value):
        """Validate query_index is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Query index must be non-negative")
        return value
    
    def validate(self, data):
        """Additional validation"""
        # Ensure required fields are present
        if not data.get('video_name'):
            raise serializers.ValidationError("video_name is required")
        if not data.get('url'):
            raise serializers.ValidationError("url is required")
        if data.get('frame_index') is None:
            raise serializers.ValidationError("frame_index is required")
        return data

class TeamAnswerSerializer(serializers.ModelSerializer):
    """Serializer for TeamAnswer model"""
    
    class Meta:
        model = TeamAnswer
        fields = [
            'id', 'video_name', 'frame_index', 'url', 'qa', 
            'query_index', 'round', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_round(self, value):
        """Validate round field"""
        if value not in ['prelims', 'final']:
            raise serializers.ValidationError("Round must be either 'prelims' or 'final'")
        return value
    
    def validate_frame_index(self, value):
        """Validate frame_index is positive"""
        if value < 0:
            raise serializers.ValidationError("Frame index must be non-negative")
        return value
    
    def validate_query_index(self, value):
        """Validate query_index is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Query index must be non-negative")
        return value


class TeamAnswerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating TeamAnswer"""
    
    class Meta:
        model = TeamAnswer
        fields = ['video_name', 'frame_index', 'url', 'qa', 'query_index', 'round']
    
    def validate_round(self, value):
        """Validate round field"""
        if value not in ['prelims', 'final']:
            raise serializers.ValidationError("Round must be either 'prelims' or 'final'")
        return value
    
    def validate_frame_index(self, value):
        """Validate frame_index is positive"""
        if value < 0:
            raise serializers.ValidationError("Frame index must be non-negative")
        return value
    
    def validate_query_index(self, value):
        """Validate query_index is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Query index must be non-negative")
        return value
    
    def validate(self, data):
        """Additional validation"""
        # Ensure required fields are present
        if not data.get('video_name'):
            raise serializers.ValidationError("video_name is required")
        if not data.get('url'):
            raise serializers.ValidationError("url is required")
        if data.get('frame_index') is None:
            raise serializers.ValidationError("frame_index is required")
        
        # Check for uniqueness of video_name, frame_index, query_index combination
        video_name = data.get('video_name')
        frame_index = data.get('frame_index')
        query_index = data.get('query_index', 0)
        
        # If this is an update (instance exists), exclude current instance from uniqueness check
        if hasattr(self, 'instance') and self.instance:
            existing = TeamAnswer.objects.filter(
                video_name=video_name,
                frame_index=frame_index,
                query_index=query_index
            ).exclude(id=self.instance.id)
        else:
            existing = TeamAnswer.objects.filter(
                video_name=video_name,
                frame_index=frame_index,
                query_index=query_index
            )
        
        if existing.exists():
            raise serializers.ValidationError(
                f"A team answer already exists for video '{video_name}', frame {frame_index}, query index {query_index}"
            )
        
        return data
