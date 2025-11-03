# An OCR-RAG-Large Language Model-Based Tutoring System for Graduate Entrance Exam Mathematics Problems

## Background
This code was made for the Computer Vision Course Project on 2025 Fall Semster.  
It is designed for improving the solving accuracy of hard and complex math problems many undergraduates may meet when perparing for the exam.

## Introduction
The project processes given math problem in three steps:  
1. OCR the problem in the picture using Doubao LLM  
2. Using RAG to search revelant knowledge in the database  
3. Supplement the retrieved knowledge into the context and use Doubao LLM again to obtain the result.  
   
An streamlit UI has been designed to compile with the whole process, making it easy to use.

## Dataset
Already build-up database has been contained into the project, if you have supplemental konwledge which needs to be added, you can modify `embedding.py` to create a new one.

## Requirement
- faiss-cpu>=1.12.0
- numpy>=1.25.0
- volcengine-python-sdk[ark]>=4.0.31
- streamlit>=1.28.0
- Pillow>=10.0.0

## Run
Just run  
```
python main.py
```