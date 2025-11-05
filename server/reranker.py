import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Union, Set


class Reranker:
    """
    Rerank for mutil model retrieval.

    supose:
    - we use N models
    - r_i(d) is the rank order of doc d in model i-th
    - s() is the function convert from rank order into score ranging from 0 -> 1

    fusion_score(d) = N * product up all s(r_i(d)) / sum up all s(r_i(d))
    """
    def __init__(self):
        pass

    def _get_rank_order(
        self, 
        indices: np.array, 
        unique_index: np.array, 
        out_top_order: int = None
    )-> np.array:
        
        """
        Get order of the given unique indexes in the indices.
    
        Args:
        indices -- np.array, shape (k,) the indices resulted from index.search, is the sorted list of the candidates.
        unique_index -- np.array,  shape (n,),  the list of index of candidates you want to check its order.
        out_top_order  -- int , The rank order of the candidates not in indices.

        Return:
            np.array, shape(n,) the which the i-th element is the order of unique_index[i]
        """
        if out_top_order is None:
            out_top_order = int(indices.shape[0] * 1.3)
        
        rank_order = np.full(unique_index.shape, out_top_order)
        
        in_top_mask = np.isin(unique_index,indices)
        in_top = unique_index[in_top_mask]
        in_top_rank_oder = [np.where(indices == x)[0][0].item() for x in in_top]
        
        rank_order[in_top_mask] = np.array(in_top_rank_oder)
        
        return rank_order
        

    def _calculate_rank_score(
        self, 
        rank_order: np.array, 
        initial_k: int, 
        alpha: float = 1.0, 
        beta : float =1.5, 
        cutoff : int = None
    ) -> np.array:
        
        """
        function convert rank order into score ranging from 0 -> 1
        
        Args:
        rank_order -- np.array, shape (initial_k,), the initial rank order of the given list unique indexes
        initial_k -- int, is the k highest in the initial rank order
        alpha -- float, positive, the scale parameter helps to scale down the low ranks strongly.
        cutoff -- int, positive, the boundary that candidates after it will apply the heavier scaling (like we wan to treat some heading candidates nicer and punish the behind ones heavier)
        beta -- float, positive, the scale parameter use for cutoff, need to be bigger than alpha
        
        Return:
        np.array, the score
        """
        if cutoff is None:
            cutoff  = rank_order.shape[0]
            
        return np.where(
          rank_order >= cutoff,
          np.exp(-alpha * cutoff/initial_k) * np.exp(-beta*(rank_order - cutoff)/initial_k),
            np.exp(-alpha * rank_order/initial_k),
          )

    def _rerank_by_rank_order(
        self, 
        list_indices:Union[Tuple[np.array], List[np.array]], 
        top_k: int = None,
        alpha: float = 1.0, 
        beta : float =0.5, 
        cutoff : int = 0, 
        out_top_order = None, 
        **kwargs) -> Tuple[np.array, np.array]:
        
        """
        Rerank the candidates resulted from multi model search.

        Args:
        list_indices -- Tuple[np.array] or List[np.array], is the list of candidates resulted from multi model search. Each np.array has shape [num_queries, inital_k].
        top_k -- int , The top k heighest ones we want to keep.
        alpha -- float, positive, the scale parameter helps to scale down the low ranks strongly.
        cutoff -- int, positive, the boundary that candidates after it will apply the heavier scaling (like we wan to treat some heading candidates more important and punish the behind ones heavier)
        beta -- float, positive, the scale parameter use for cutoff
        out_top_order -- int, The rank order of the candidates not in indices.
        
        Returns:
            Tuple(np.array, np.array), (scores, indices)
        """

        num_queries = list_indices[0].shape[0]
        num_models = len(list_indices)
        initial_k = list_indices[0].shape[1]
        
        if top_k is None:
            top_k = initial_k

        # merge all candidates , preparing for process of creating unique index
        all_candidates = np.empty((num_queries,0))
        for indice in list_indices:
            all_candidates = np.concatenate((all_candidates, indice), axis = 1)

        # rerank
        scores = []
        indices = []
        # go through each query
        for i in range(num_queries):
            # some time i use idx for the candidate
            unique_idx = np.unique(all_candidates[i]).astype(int)

            # list score calculated from rank order of all model, 
            # rank_scores[i] is the rank score of the order from model i_th
            rank_scores = []
            for j in range(num_models):
               rank_order = self._get_rank_order(list_indices[j][i], unique_idx, out_top_order)
               rank_score = self._calculate_rank_score(rank_order, initial_k =initial_k,  alpha = alpha, beta = beta, cutoff = cutoff)
               rank_scores.append(rank_score)

            # calculate the fusion score, this type of score will be use for reranking
            emnumerator = np.prod(rank_scores, axis = 0)
            denominator = np.sum(rank_scores, axis = 0)
            fusion_score = num_models * emnumerator / denominator

            # sort and get top k
            rerank_indices = np.argsort(-fusion_score)[:top_k]
            rerank_scores = fusion_score[rerank_indices]

            scores.append(rerank_scores)
            indices.append(unique_idx[rerank_indices])

        return (np.array(scores), np.array(indices))

    def _get_unique_paths(self, batch_result: List[List[Tuple[str, float]]]) -> Set[str]:
        num_queries = len(batch_result)
        paths = []
        for result in batch_result:
            path = [i[0] for i in result]
            paths.extend(path)
            
        return set(paths)

    def _create_gobal_mapping(self, list_paths : List[Set[str]]):
        all_paths = list_paths[0]
        for i in range(1,len(list_paths)):
            all_paths = all_paths | list_paths[i]

        path2id = {path : i for i,path in enumerate(all_paths)}
        id2path = {i : path for path, i in path2id.items()}
        return [path2id, id2path]

    def _reconstruct_batch_result_into_scores_indices(self, batch_result, path2id):
        batch_scores = []
        batch_indices = []
        for result in batch_result:
            scores = [i[1] for i in result]
            indices = [path2id[i[0]] for i in result]
            batch_scores.append(scores)
            batch_indices.append(indices)
            
        batch_indices = np.array(batch_indices).astype(int)
        batch_scores = np.array(batch_scores)

        return tuple([batch_scores, batch_indices])
        
    def _reconstruct_scores_indices_into_batch_result(self, scores_batch, indices_batch, id2path):
        batch_results = []
        for scores, indices in zip(scores_batch, indices_batch):
            single_query_results = []
            for score, idx in zip(scores, indices):
                single_query_results.append((id2path[idx], float(score)))
            batch_results.append(single_query_results)
        return batch_results
    
    def __call__(
        self,
        list_batch_result : List[List[List[Tuple[str, float]]]] = None,
        list_indices:Union[Tuple[np.array], List[np.array]] = None, 
        top_k: int = None, 
        **kwargs 
    ) -> Union[Tuple[np.array, np.array], List[List[Tuple[str, float]]]] :

        # convert batch result from mutil model into a unified index
        if list_batch_result is not None:
            all_path = [self._get_unique_paths(i) for i in list_batch_result]
            path2id, id2path = self._create_gobal_mapping(all_path)

            list_indices = []
            list_scores = []
            for batch_result in list_batch_result:
                scores, indices = self._reconstruct_batch_result_into_scores_indices(batch_result, path2id)
                list_indices.append(indices)
                list_scores.append(scores)

        # reranking
        scores, indices = self._rerank_by_rank_order(
            list_indices = list_indices,
            top_k = top_k,
            **kwargs
        )

        if list_batch_result is not None:
            result = self._reconstruct_scores_indices_into_batch_result(scores, indices, id2path)
            return result
            
        return tuple([scores, indices])