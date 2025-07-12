from rest_framework import serializers
from .models import Query, QuerySession

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
        # Handle empty string as null (when user wants to remove image)
        if value == '':
            return None
            
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image file too large ( > 10MB )")
            
            # Check file type
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("File is not an image")
        
        return value

    def update(self, instance, validated_data):
        """Custom update method to handle image file deletion"""
        # Store old image before updating
        old_image = instance.image
        
        # Check if image is being updated or removed
        if 'image' in validated_data:
            new_image = validated_data['image']
            
            # If image is being removed (None) or replaced with new image
            if new_image != old_image:
                # Delete old image file if it exists
                if old_image:
                    instance.delete_image_file()
        
        # Perform the update
        return super().update(instance, validated_data)
