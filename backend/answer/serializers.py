from rest_framework import serializers
from .models import Answer, TeamAnswer

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
