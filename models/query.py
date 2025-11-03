import base64
import os
import pickle
import faiss
import numpy as np
from volcenginesdkarkruntime import Ark
from typing import List, Dict, Any

class MathProblemSolver:
    def __init__(self, api_key: str):
        self.client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=api_key,
        )
        self._load_vector_index()
        
    def _load_vector_index(self):
        try:
            self.index = faiss.read_index("index/math_ocr_index.faiss")
            with open("index/math_ocr_index.pkl", "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict) and 'texts' in data:
                self.knowledge_data = data['texts']
            else:
                self.knowledge_data = data
        except Exception as e:
            print(f"Failed to load vector index: {e}")
            self.index = None
            self.knowledge_data = []
    
    def encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_problem_text(self, image_path: str) -> str:
        image_format = image_path.split('.')[-1].lower()
        if image_format not in ['jpg', 'jpeg', 'png', 'webp']:
            image_format = 'jpeg'
            
        base64_image = self.encode_image(image_path)
        
        completion = self.client.chat.completions.create(
            model="doubao-seed-1-6-vision-250815",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            },         
                        },
                        {
                            "type": "text",
                            "text": """请识别这张图片中的数学题目，将题目内容完整地提取出来。要求：
                            1. 保持题目的原始结构和格式
                            2. 数学公式请用LaTeX格式表示
                            3. 只输出题目内容，不要添加其他解释
                            4. 如果是选择题，请完整列出所有选项
                            5. 确保文本准确无误"""
                        },
                    ],
                }
            ],
        )
        
        return completion.choices[0].message.content
    
    def get_embedding(self, text: str) -> np.ndarray:
        resp = self.client.embeddings.create(
            model="doubao-embedding-text-240715",
            input=[text],
            encoding_format="float",
        )
        embedding = np.array(resp.data[0].embedding, dtype=np.float32)
        return embedding.reshape(1, -1)
    
    def search_related_knowledge(self, problem_text: str, top_k: int = 3) -> List[str]:
        if self.index is None:
            return ["Vector index not loaded successfully, unable to retrieve related knowledge"]
        
        query_embedding = self.get_embedding(problem_text)
        
        if query_embedding.shape[1] != self.index.d:
            if query_embedding.shape[1] > self.index.d:
                query_embedding = query_embedding[:, :self.index.d]
            elif query_embedding.shape[1] < self.index.d:
                padded_embedding = np.zeros((1, self.index.d), dtype=np.float32)
                padded_embedding[:, :query_embedding.shape[1]] = query_embedding
                query_embedding = padded_embedding
        
        actual_top_k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, actual_top_k)
        
        related_knowledge = []
        for idx_array in indices:
            for idx in idx_array:
                if idx != -1 and 0 <= idx < len(self.knowledge_data):
                    related_knowledge.append(self.knowledge_data[idx])
        
        if not related_knowledge:
            related_knowledge = self.get_fallback_knowledge(problem_text)
        
        return related_knowledge
    
    def get_fallback_knowledge(self, problem_text: str) -> List[str]:
        fallback_knowledge = [
            "数学题目解答需要注意审题，理解题目要求",
            "解题过程中要注意公式的推导和计算步骤",
            "数学问题通常涉及基本概念、定理和公式的应用"
        ]
        
        if any(keyword in problem_text for keyword in ["微积分", "导数", "积分"]):
            fallback_knowledge.extend([
                "微积分基本定理：导数和积分是互逆运算",
                "常见函数的导数公式需要熟记",
                "积分计算要注意积分上下限和积分变量"
            ])
        elif any(keyword in problem_text for keyword in ["线性代数", "矩阵", "向量"]):
            fallback_knowledge.extend([
                "矩阵运算要符合维度规则",
                "向量空间的基本性质需要掌握",
                "线性方程组的解法有多种，如高斯消元法"
            ])
        elif any(keyword in problem_text for keyword in ["概率", "统计"]):
            fallback_knowledge.extend([
                "概率计算要注意事件的独立性和互斥性",
                "常见概率分布的特点和应用场景",
                "统计推断基于样本对总体进行估计"
            ])
        
        return fallback_knowledge
    
    def solve_math_problem(self, problem_text: str, related_knowledge: List[str]) -> str:
        knowledge_context = "\n".join([f"- {knowledge}" for knowledge in related_knowledge])
        
        prompt = f"""请解答以下数学题目：

题目：
{problem_text}

相关知识点：
{knowledge_context}

请按照以下要求进行解答：
1. 分析题目考查的知识点
2. 给出详细的解题步骤
3. 使用LaTeX格式表示数学公式
4. 最终给出答案
5. 如果题目有多个小问，请分别解答

请开始解答："""

        completion = self.client.chat.completions.create(
            model="doubao-seed-1-6-vision-250815",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )
        
        return completion.choices[0].message.content
    
    def process_math_problem(self, image_path: str) -> Dict[str, Any]:
        result = {
            "problem_text": "",
            "related_knowledge": [],
            "solution": "",
            "success": False
        }
        
        try:
            print("Step 1: Extracting problem content...")
            problem_text = self.extract_problem_text(image_path)
            result["problem_text"] = problem_text
            
            print("Step 2: Retrieving related knowledge points...")
            related_knowledge = self.search_related_knowledge(problem_text)
            result["related_knowledge"] = related_knowledge
            
            print("Step 3: Generating solution...")
            solution = self.solve_math_problem(problem_text, related_knowledge)
            result["solution"] = solution
            result["success"] = True
            
            print("Solution completed!")
            
        except Exception as e:
            print(f"Error during processing: {e}")
            result["error"] = str(e)
        
        return result

def main():
    api_key = os.getenv('ARK_API_KEY')
    if not api_key:
        print("Please set the ARK_API_KEY environment variable")
        return
    
    solver = MathProblemSolver(api_key)
    image_path = "640.png"
    
    if os.path.exists(image_path):
        result = solver.process_math_problem(image_path)
        
        if result["success"]:
            print(f"\nExtracted problem:\n{result['problem_text']}")
            print(f"\nRelated knowledge points:")
            for i, knowledge in enumerate(result["related_knowledge"], 1):
                print(f"{i}. {knowledge}")
            print(f"\nSolution:\n{result['solution']}")
        else:
            print(f"Processing failed: {result.get('error', 'Unknown error')}")
    else:
        print(f"Image file does not exist: {image_path}")

if __name__ == "__main__":
    main()
