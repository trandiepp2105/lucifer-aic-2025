package dev.dres.api.rest.types.collection

import kotlinx.serialization.Serializable

/**
 * Response class for bulk import results.
 *
 * @author Generated
 * @version 1.0.0
 */
@Serializable
data class ApiBulkImportResult(
    val success: Boolean,
    val totalItems: Int,
    val importedItems: Int,
    val skippedItems: Int,
    val errorItems: Int,
    val message: String,
    val skippedItemNames: List<String> = emptyList(),
    val errorItemNames: List<String> = emptyList()
)
