import numpy as np
import open_clip
import torch
from typing import List, Any


class CLIPEmbedder:
    """
    CLIP Embedder được tối ưu để chạy trên một GPU cụ thể.
    Đã loại bỏ logic DataParallel không cần thiết.
    """
    
    def __init__(self, device, model_name="ViT-H-14-quickgelu", pretrained="dfn5b", tokenizer_model=None):
        """
        Khởi tạo Embedder trên một device cụ thể (ví dụ: "cuda:0").
        """
        self.device = device
        self.model_name = model_name
        self.pretrained = pretrained
        # Nếu tokenizer_model không được cung cấp, mặc định sẽ dùng model_name
        self.tokenizer_model = tokenizer_model if tokenizer_model else model_name
        
        print(f"  -> Loading model '{self.model_name}' with pretrained '{self.pretrained}' onto device '{self.device}'...")
        self._load_model()
        
    def _load_model(self):
        """Load CLIP model, preprocess, và tokenizer lên device đã chỉ định."""
        try:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, 
                pretrained=self.pretrained,
                device=self.device
            )
            self.tokenizer = open_clip.get_tokenizer(self.tokenizer_model)
            self.model.eval()
        except Exception as e:
            print(f"❌ Failed to load model {self.model_name} on {self.device}. Error: {e}")
            raise e
    
    def encode_image(self, image):
        try:
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.amp.autocast(self.device.type, enabled=self.device.type == 'cuda'):
                with torch.no_grad():
                    embedding = self.model.encode_image(image_tensor)
                    embedding_norm = torch.nn.functional.normalize(embedding, p=2, dim=-1)
            result = embedding_norm.cpu().numpy().flatten()
            del image_tensor, embedding, embedding_norm
            if self.device.type == 'cuda': 
                torch.cuda.empty_cache()
            return result
        except Exception as e:
            print(f"❌ Image encoding failed for model {self.model_name} on {self.device}: {e}")
            if self.device.type == 'cuda': torch.cuda.empty_cache()
            return None
    
    def encode_text(self, text):
        try:
            text_tokens = self.tokenizer([text]).to(self.device)
            with torch.amp.autocast(self.device.type, enabled=self.device.type == 'cuda'):
                with torch.no_grad():
                    embedding = self.model.encode_text(text_tokens)
                    embedding_norm = torch.nn.functional.normalize(embedding, p=2, dim=-1)
            result = embedding_norm.cpu().numpy().flatten()
            del text_tokens, embedding, embedding_norm
            if self.device.type == 'cuda': 
                torch.cuda.empty_cache()
            return result
        except Exception as e:
            print(f"❌ Text encoding failed for model {self.model_name} on {self.device}: {e}")
            if self.device.type == 'cuda': torch.cuda.empty_cache()
            return None

    def encode_batch(self, queries: List[Any]) -> np.ndarray:
        text_queries = [(i, q) for i, q in enumerate(queries) if isinstance(q, str)]
        image_queries = [(i, q) for i, q in enumerate(queries) if not isinstance(q, str)]
        
        final_embeddings = [None] * len(queries)
        
        if text_queries:
            indices, texts = zip(*text_queries)
            text_tokens = self.tokenizer(list(texts)).to(self.device)
            with torch.amp.autocast(self.device.type, enabled=self.device.type == 'cuda'):
                with torch.no_grad():
                    text_embeds = self.model.encode_text(text_tokens)
                    text_embeds = torch.nn.functional.normalize(text_embeds, p=2, dim=-1)
            for i, idx in enumerate(indices):
                final_embeddings[idx] = text_embeds[i].cpu().numpy()

        if image_queries:
            indices, images = zip(*image_queries)
            image_tensors = torch.stack([self.preprocess(img) for img in images]).to(self.device)
            with torch.amp.autocast(self.device.type, enabled=self.device.type == 'cuda'):
                with torch.no_grad():
                    image_embeds = self.model.encode_image(image_tensors)
                    image_embeds = torch.nn.functional.normalize(image_embeds, p=2, dim=-1)
            for i, idx in enumerate(indices):
                final_embeddings[idx] = image_embeds[i].cpu().numpy()

        return np.array(final_embeddings, dtype=np.float32)
