from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline as hf_pipeline, pipeline
import os

app = FastAPI()

# Allow frontend requests (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL if needed
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Load models once
# -------------------------------
# General video classification
general_model = hf_pipeline(
    "video-classification",
    model="MCG-NJU/videomae-base-finetuned-kinetics",
    framework="pt"
)

# Crime video classification
crime_model = hf_pipeline(
    "video-classification",
    model="owinymarvin/timesformer-crime-detection",
    framework="pt"
)

# Image classification model (CPU-friendly)
image_model = hf_pipeline(
    "image-classification",
    model="google/vit-base-patch16-224"
)

# Text generation model
text_generator = pipeline(
    "text2text-generation",
    model="google/flan-t5-small"
)

# -------------------------------
# Helper functions
# -------------------------------
def classify_video(video_path, model_type: str):
    """Classify video using selected model type."""
    if model_type == "general":
        preds = general_model(video_path)
    elif model_type == "crime":
        preds = crime_model(video_path)
    else:
        raise ValueError("Invalid model type. Choose 'general' or 'crime'.")
    
    # Top 5 labels with scores
    top5 = [{"label": pred['label'], "score": round(pred['score'], 3)} for pred in preds[:5]]
    
    # Top 2 labels for text generation
    top2_labels = [pred['label'] for pred in preds[:2]]
    return top5, top2_labels

def classify_image(file_path):
    """Classify an image using the image model."""
    preds = image_model(file_path)
    top5 = [{"label": pred['label'], "score": round(pred['score'], 3)} for pred in preds[:5]]
    return top5

def labels_to_sentence(top2_labels):
    """Generate a single sentence describing the video using top 2 labels."""
    prompt = f"Write a single sentence that accurately describes a video showing: {', '.join(top2_labels)}."
    result = text_generator(
        prompt,
        max_new_tokens=60,
        num_return_sequences=1,
        do_sample=True,
        temperature=0.5,
        top_p=0.9
    )
    sentence = result[0]['generated_text'].replace(prompt, '').strip()
    return sentence

# -------------------------------
# API endpoint
# -------------------------------
@app.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    model_type: str = Form(...)  # 'general', 'crime', or 'image'
):
    temp_path = f"temp_{file.filename}"
    
    # Save uploaded file
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    try:
        if model_type in ["general", "crime"]:
            top5_labels, top2_labels = classify_video(temp_path, model_type)
            description = labels_to_sentence(top2_labels)
            return {
                "model_type": model_type,
                "top5_labels": top5_labels,
                "description": description
            }
        elif model_type == "image":
            top5_labels = classify_image(temp_path)
            return {
                "model_type": "image",
                "top5_labels": top5_labels
            }
        else:
            return {"error": "Invalid model_type. Choose 'general', 'crime', or 'image'."}
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

# -------------------------------
# Run locally
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
