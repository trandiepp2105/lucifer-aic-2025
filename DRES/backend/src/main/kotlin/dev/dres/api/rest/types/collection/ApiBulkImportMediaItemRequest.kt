package dev.dres.api.rest.types.collection

import kotlinx.serialization.Serializable

/**
 * Request class for bulk importing media items from JSON.
 *
 * @author Generated
 * @version 1.0.0
 */
@Serializable
data class ApiBulkImportMediaItemRequest(
    val collectionId: String,
    val videoItems: List<ApiCreateMediaItemRequest>
) {
    init {
        require(videoItems.isNotEmpty()) { "Video items list cannot be empty." }
        require(videoItems.all { it.collectionId == collectionId }) { "All items must belong to the same collection." }
    }
}
