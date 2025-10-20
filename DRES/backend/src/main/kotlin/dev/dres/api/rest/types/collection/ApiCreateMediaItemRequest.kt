package dev.dres.api.rest.types.collection

import dev.dres.data.model.media.*
import kotlinx.serialization.Serializable

/**
 * Request class for creating new media items (without mediaItemId).
 *
 * @author Generated
 * @version 1.0.0
 */
@Serializable
data class ApiCreateMediaItemRequest(
    val name: String,
    val type: ApiMediaType,
    val collectionId: String,
    val location: String,
    val durationMs: Long? = null,
    val fps: Float? = null,
    val metadata: List<ApiMediaItemMetaDataEntry> = emptyList()
) {
    init {
        if (this.type == ApiMediaType.VIDEO) {
            require(this.durationMs != null) { "Duration must be set for a video item." }
            require(this.fps != null) { "FPS must be set for a video item." }
        }
    }
    
    /**
     * Convert to ApiMediaItem with auto-generated ID
     */
    fun toApiMediaItem(generatedId: MediaItemId): ApiMediaItem {
        return ApiMediaItem(
            mediaItemId = generatedId,
            name = name,
            type = type,
            collectionId = collectionId,
            location = location,
            durationMs = durationMs,
            fps = fps,
            metadata = metadata
        )
    }
}
