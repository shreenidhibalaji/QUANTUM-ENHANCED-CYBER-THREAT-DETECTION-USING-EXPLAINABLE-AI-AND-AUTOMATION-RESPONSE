<<<<<<< HEAD
import torch


from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

import qrcode
import socket
import os

from fpdf import FPDF
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash, session
import os
import pandas as pd
import numpy as np
import uuid
from datetime import datetime
import sqlite3
import threading
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from twilio.rest import Client
import pickle
import shap
import warnings
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt
import time

# Environment variables (create a .env file with these)
from dotenv import load_dotenv
load_dotenv()

# Import your model components
#import torch
import ipaddress
import re
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn
import torch.nn.functional as F

app = Flask(__name__)
def get_local_ip():
    return socket.gethostbyname(socket.gethostname())

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this-in-production')

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)
os.makedirs("database", exist_ok=True)
os.makedirs("models", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("shap_results", exist_ok=True)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'txt', 'pcap'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Email Configuration (from .env)
EMAIL_CONFIG = {
    'smtp_server': os.getenv('EMAIL_HOST', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('EMAIL_PORT', 587)),
    'email': os.getenv('EMAIL_ADDRESS'),
    'password': os.getenv('EMAIL_PASSWORD')
}

# Twilio Configuration (from .env)
TWILIO_CONFIG = {
    'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
    'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
    'phone_number': os.getenv('TWILIO_PHONE_NUMBER')
}

# Alert thresholds
ATTACK_THRESHOLD = 0.01 # 30% threshold for attack detection (as requested)

# Your QNN Model Classes
class ImprovedNN(nn.Module):
    def __init__(self, input_size, num_classes):
        super(ImprovedNN, self).__init__()
        
        # Layer normalization for better training stability
        self.input_norm = nn.LayerNorm(input_size)
        
        # Deeper network with residual connections
        self.fc1 = nn.Linear(input_size, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.dropout1 = nn.Dropout(0.3)
        
        self.fc2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.dropout2 = nn.Dropout(0.4)
        
        self.fc3 = nn.Linear(128, 64)
        self.bn3 = nn.BatchNorm1d(64)
        self.dropout3 = nn.Dropout(0.3)
        
        self.fc4 = nn.Linear(64, 32)
        self.bn4 = nn.BatchNorm1d(32)
        self.dropout4 = nn.Dropout(0.2)
        
        self.fc5 = nn.Linear(32, num_classes)
        
    def forward(self, x):
        # Input normalization
        x = self.input_norm(x)
        
        # Layer 1
        x1 = F.relu(self.bn1(self.fc1(x)))
        x1 = self.dropout1(x1)
        
        # Layer 2
        x2 = F.relu(self.bn2(self.fc2(x1)))
        x2 = self.dropout2(x2)
        
        # Layer 3
        x3 = F.relu(self.bn3(self.fc3(x2)))
        x3 = self.dropout3(x3)
        
        # Layer 4
        x4 = F.relu(self.bn4(self.fc4(x3)))
        x4 = self.dropout4(x4)
        
        # Output layer
        output = self.fc5(x4)
        
        return output

# Global variables for models
qnn_model = None
float_model = None
label_encoder = None
scaler = None
shap_explainer = None
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def load_models():
    """Load your trained QNN and float models"""
    global qnn_model, float_model, label_encoder, scaler, shap_explainer
    
    try:
        # Check if model files exist
        float_model_path = 'models/improved_float_model.pth'
        quant_model_path = 'models/improved_quantized_model.pth'
        
        if not os.path.exists(float_model_path):
            print(f"❌ Float model not found at {float_model_path}")
            return False
        
        # Load float model
        print("Loading float model...")
        try:
            float_checkpoint = torch.load(float_model_path, map_location='cpu', weights_only=False)
            
            # Initialize the model
            float_model = ImprovedNN(
                float_checkpoint['input_size'], 
                float_checkpoint['num_classes']
            )
            float_model.load_state_dict(float_checkpoint['model_state_dict'])
            float_model.eval()
            
            # Load preprocessing components
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                label_encoder = float_checkpoint['label_encoder']
                scaler = float_checkpoint['scaler']
            
            print("✅ Float model loaded successfully!")
            
        except Exception as e:
            print(f"❌ Error loading float model: {e}")
            return False
        
        # Try to load quantized model
        print("Loading quantized model...")
        try:
            if os.path.exists(quant_model_path):
                quant_checkpoint = torch.load(quant_model_path, map_location='cpu', weights_only=False)
                qnn_model = quant_checkpoint['model']
                print("✅ Quantized model loaded successfully!")
            else:
                print("⚠️  Quantized model not found, using float model for predictions")
                qnn_model = float_model
                
        except Exception as e:
            print(f"⚠️  Error loading quantized model: {e}")
            qnn_model = float_model
        
        # Try to load SHAP explainer
        print("Loading SHAP explainer...")
        try:
            shap_explainer_path = 'shap_results\shap_explainer.pkl'
            if os.path.exists(shap_explainer_path):
                with open(shap_explainer_path, 'rb') as f:
                    shap_explainer = pickle.load(f)
                print("✅ SHAP explainer loaded successfully!")
            else:
                print("⚠️  SHAP explainer not found, SHAP analysis will be skipped")
                
        except Exception as e:
            print(f"⚠️  Error loading SHAP explainer: {e}")
            shap_explainer = None
        
        print(f"✅ Models loaded successfully!")
        print(f"   Model input size: {float_checkpoint['input_size']}")
        print(f"   Model classes: {float_checkpoint['num_classes']}")
        print(f"   Label encoder classes: {label_encoder.classes_}")
        print(f"   Device: {device}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading models: {e}")
        return False

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    ''')
    
    # Create analysis history table
    c.execute('''
    CREATE TABLE IF NOT EXISTS analysis_history (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        analysis_type TEXT,
        filename TEXT,
        total_records INTEGER,
        attack_records INTEGER,
        attack_percentage REAL,
        result TEXT,
        alert_sent BOOLEAN DEFAULT 0,
        shap_analysis BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create alert logs table
    c.execute('''
    CREATE TABLE IF NOT EXISTS alert_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id TEXT,
        alert_type TEXT,
        recipient TEXT,
        status TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (analysis_id) REFERENCES analysis_history (id)
    )
    ''')

 


    conn.commit()
    conn.close()



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_address_to_numeric(address):
    """Convert IP/MAC addresses to numeric format"""
    if ':' in str(address):  # MAC address
        mac_address = re.sub(r':', '', str(address))
        try:
            return int(mac_address, 16)
        except ValueError:
            return 0
    else:  # IPv4 address
        try:
            return int(ipaddress.IPv4Address(str(address)))
        except ValueError:
            return 0

def get_training_protocol_mapping():
    """Get the exact protocol mapping used during training from final.csv"""
    try:
        # Try to load final.csv to get the exact protocol distribution used in training
        final_csv_paths = [
            'final.csv',
            'data/final.csv', 
            '../final.csv',
            '/kaggle/input/finaldataset/final.csv'  # Common Kaggle path
        ]
        
        final_df = None
        for path in final_csv_paths:
            if os.path.exists(path):
                print(f"📁 Found final.csv at: {path}")
                final_df = pd.read_csv(path)
                break
        
        if final_df is not None and 'Protocol' in final_df.columns:
            # Get the top 10 protocols from training data
            top_protocols = final_df['Protocol'].value_counts().head(10).index.tolist()
            print(f"✅ Extracted training protocols from final.csv: {top_protocols}")
            return top_protocols
        else:
            print("⚠️ Could not load final.csv, using fallback protocol list")
    except Exception as e:
        print(f"⚠️ Error loading final.csv: {e}")
    
    # Fallback: Based on common protocols seen in network traffic datasets
    return [
        'RTP', 'DISCARD', 'SIP', 'TCP', 'UDP', 
        'SSH', 'RTCP', 'STUN', 'CLASSIC-STUN', 'RTP EVENT'
    ]

def preprocess_data_for_model(df):
    """Enhanced preprocessing with EXACT match to training preprocessing using final.csv reference"""
    print(f"📊 Starting preprocessing for {len(df)} records...")
    
    # Make a copy
    processed_df = df.copy()
    
    # Handle missing values first
    print(f"Missing values before processing:\n{processed_df.isnull().sum()}")
    
    # Filter addresses with '.' or ':' (more robust)
    if 'Source' in processed_df.columns and 'Destination' in processed_df.columns:
        source_mask = processed_df['Source'].astype(str).apply(lambda x: '.' in x or ':' in x)
        dest_mask = processed_df['Destination'].astype(str).apply(lambda x: '.' in x or ':' in x)
        processed_df = processed_df[source_mask & dest_mask]
        print(f"After filtering addresses: {processed_df.shape}")
        
        # Convert addresses to numeric
        processed_df['Source'] = processed_df['Source'].apply(convert_address_to_numeric)
        processed_df['Destination'] = processed_df['Destination'].apply(convert_address_to_numeric)
        
        # Convert to float and handle any remaining issues
        processed_df['Source'] = pd.to_numeric(processed_df['Source'], errors='coerce')
        processed_df['Destination'] = pd.to_numeric(processed_df['Destination'], errors='coerce')
    
    # Drop unnecessary columns
    columns_to_drop = ['No.', 'Info', 'Unnamed: 0']
    for col in columns_to_drop:
        if col in processed_df.columns:
            processed_df = processed_df.drop(col, axis=1)
            print(f"Dropped column: {col}")
    
    # Handle Protocol column with EXACT same encoding as training (using final.csv reference)
    if 'Protocol' in processed_df.columns:
        print(f"Protocol value counts before mapping:\n{processed_df['Protocol'].value_counts()}")
        
        # Get the EXACT top 10 protocols from training
        training_top_protocols = get_training_protocol_mapping()
        print(f"Using training top protocols: {training_top_protocols}")
        
        # Map protocols: if in training top 10, keep it; otherwise map to 'Other'
        processed_df['Protocol'] = processed_df['Protocol'].apply(
            lambda x: x if x in training_top_protocols else 'Other'
        )
        
        print(f"Protocol mapping after training alignment:\n{processed_df['Protocol'].value_counts()}")
        
        # One-hot encode with EXACT same protocol names as training
        protocol_dummies = pd.get_dummies(processed_df['Protocol'], prefix='Protocol')
        processed_df = pd.concat([processed_df, protocol_dummies.astype(int)], axis=1)
        processed_df = processed_df.drop('Protocol', axis=1)
        print(f"Added {len(protocol_dummies.columns)} protocol features")
        print(f"Protocol features created: {list(protocol_dummies.columns)}")
    
    # Handle other categorical columns
    categorical_cols = processed_df.select_dtypes(include=['object']).columns
    for col in categorical_cols:
        if col != 'label':  # Don't encode target
            print(f"Encoding categorical column: {col}")
            if processed_df[col].nunique() > 20:
                # Too many categories, use frequency encoding
                freq_map = processed_df[col].value_counts().to_dict()
                processed_df[f'{col}_freq'] = processed_df[col].map(freq_map)
                processed_df = processed_df.drop(col, axis=1)
            else:
                # One-hot encode
                dummies = pd.get_dummies(processed_df[col], prefix=col)
                processed_df = pd.concat([processed_df, dummies.astype(int)], axis=1)
                processed_df = processed_df.drop(col, axis=1)
    
    # Handle infinite values first
    processed_df = processed_df.replace([np.inf, -np.inf], np.nan)
    
    # Separate numeric and non-numeric columns
    numeric_cols = processed_df.select_dtypes(include=[np.number]).columns.tolist()
    non_numeric_cols = processed_df.select_dtypes(exclude=[np.number]).columns.tolist()
    
    print(f"Numeric columns: {len(numeric_cols)}")
    print(f"Non-numeric columns: {non_numeric_cols}")
    
    # Fill NaN values only in numeric columns
    if len(numeric_cols) > 0:
        processed_df[numeric_cols] = processed_df[numeric_cols].fillna(processed_df[numeric_cols].median())
    
    # Keep only numeric columns (same as training)
    processed_df = processed_df[numeric_cols]
    
    print(f"Final preprocessed shape: {processed_df.shape}")
    print(f"Final columns: {list(processed_df.columns)}")
    
    return processed_df
def generate_shap_analysis(data, predictions, analysis_id):
    """
    Generate SHAP visualizations with robust error handling for all model types
    """
    global float_model, scaler, label_encoder
    import numpy as np
    
    shap_dir = f"shap_results/analysis_{analysis_id}"
    os.makedirs(shap_dir, exist_ok=True)
    plot_paths = {}
    
    try:
        print(f"🔄 Starting SHAP analysis for {analysis_id}...")
        
        if float_model is None or scaler is None:
            print("❌ Model or scaler not loaded, cannot perform SHAP analysis")
            return False, plot_paths
            
        # Preprocess data
        processed_data = preprocess_data_for_model(data)
        if len(processed_data) == 0:
            print("❌ No valid data after preprocessing for SHAP")
            return False, plot_paths
            
        aligned_data = align_features_with_training(processed_data, scaler)
        scaled_data = scaler.transform(aligned_data)
        
        # Use first sample for explanation
        sample_idx = 0
        single_row = scaled_data[sample_idx:sample_idx+1]
        single_df = pd.DataFrame(single_row, columns=aligned_data.columns)
        
        print(f"📊 SHAP sample shape: {single_row.shape}")
        print(f"📊 Feature count: {len(aligned_data.columns)}")
        
        def model_predict_proba(X):
            """Wrapper function for model predictions"""
            X_tensor = torch.tensor(X, dtype=torch.float32)
            float_model.eval()
            with torch.no_grad():
                outputs = float_model(X_tensor)
                probabilities = F.softmax(outputs, dim=1)
            return probabilities.numpy()
        
        # Create background data (smaller sample for faster computation)
        background_size = min(50, len(scaled_data))
        background_data = scaled_data[:background_size]
        
        print(f"📊 Background data shape: {background_data.shape}")
        
        # Create SHAP explainer
        explainer = shap.KernelExplainer(model_predict_proba, background_data)
        
        # Get SHAP values
        print("🔄 Computing SHAP values...")
        shap_values = explainer.shap_values(single_row)
        
        # Debug: Print shapes and types
        print(f"📊 SHAP values type: {type(shap_values)}")
        if isinstance(shap_values, list):
            print(f"📊 SHAP values list length: {len(shap_values)}")
            for i, sv in enumerate(shap_values):
                print(f"   Class {i} shape: {np.array(sv).shape}")
        else:
            print(f"📊 SHAP values shape: {np.array(shap_values).shape}")
        
        print(f"📊 Expected value type: {type(explainer.expected_value)}")
        print(f"📊 Expected value: {explainer.expected_value}")
        
        # Handle different SHAP value formats
        shap_array = np.array(shap_values)
        print(f"📊 SHAP array shape: {shap_array.shape}")
        
        # Get model prediction for this sample
        pred_probs = model_predict_proba(single_row)[0]
        predicted_class_idx = int(np.argmax(pred_probs))
        
        print(f"📊 Predicted class index: {predicted_class_idx}")
        print(f"📊 Prediction probabilities: {pred_probs}")
        
        if isinstance(shap_values, list):
            # Multi-class case: shap_values is a list
            num_classes = len(shap_values)
            print(f"📊 Multi-class model detected (list): {num_classes} classes")
            
            # Ensure we don't go out of bounds
            if predicted_class_idx >= len(shap_values):
                predicted_class_idx = 0
                print(f"⚠️ Adjusted predicted class index to 0")
            
            # Get SHAP values for predicted class
            shap_values_for_plot = np.array(shap_values[predicted_class_idx])
            if len(shap_values_for_plot.shape) > 1:
                shap_values_for_plot = shap_values_for_plot[0]  # Take first row if 2D
            
        elif len(shap_array.shape) == 3:
            # 3D array case: (samples, features, classes)
            print(f"📊 Multi-class model detected (3D array): {shap_array.shape[2]} classes")
            
            # Ensure we don't go out of bounds
            if predicted_class_idx >= shap_array.shape[2]:
                predicted_class_idx = 0
                print(f"⚠️ Adjusted predicted class index to 0")
            
            # Extract SHAP values for predicted class: shape (1, 15, 2) -> (15,)
            shap_values_for_plot = shap_array[0, :, predicted_class_idx]
            
        elif len(shap_array.shape) == 2:
            # 2D array case: (samples, features) - single class
            print("📊 Single class model detected (2D array)")
            shap_values_for_plot = shap_array[0]  # Take first sample
            
        else:
            # 1D array case: (features,) - single class, single sample
            print("📊 Single class model detected (1D array)")
            shap_values_for_plot = shap_array
        
        # Handle base value
        if isinstance(explainer.expected_value, np.ndarray):
            if len(explainer.expected_value) > predicted_class_idx:
                base_value = explainer.expected_value[predicted_class_idx]
            else:
                base_value = explainer.expected_value[0]
        else:
            base_value = explainer.expected_value
        
        print(f"📊 Final SHAP values shape: {shap_values_for_plot.shape}")
        print(f"📊 Base value: {base_value}")
        
        # Set dark theme for plots
        plt.style.use('dark_background')
        
        # 1. Create Summary Plot (Bar plot - most reliable)
        try:
            print(f"📊 Creating summary plot with SHAP values shape: {shap_values_for_plot.shape}")
            
            plt.figure(figsize=(10, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                print(f"⚠️ SHAP values still multi-dimensional: {shap_values_for_plot.shape}")
                shap_values_for_plot = shap_values_for_plot.flatten()
            
            # Create feature importance data
            feature_names = list(single_df.columns)
            abs_shap_values = np.abs(shap_values_for_plot)
            
            print(f"📊 Feature names length: {len(feature_names)}")
            print(f"📊 SHAP values length: {len(shap_values_for_plot)}")
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_values_for_plot))
            feature_names = feature_names[:min_length]
            abs_shap_values = abs_shap_values[:min_length]
            
            # Sort by importance
            sorted_indices = np.argsort(abs_shap_values)[::-1]
            top_n = min(15, len(sorted_indices))  # Top 15 features or less
            top_features = sorted_indices[:top_n]
            
            top_feature_names = [feature_names[i] for i in top_features]
            top_shap_values = abs_shap_values[top_features]
            
            # Create horizontal bar plot
            y_pos = np.arange(len(top_feature_names))
            bars = plt.barh(y_pos, top_shap_values, color='skyblue')
            
            plt.yticks(y_pos, top_feature_names)
            plt.xlabel('SHAP Value (Absolute)')
            plt.title('Top Feature Importance (SHAP Analysis)', fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()  # Highest importance at top
            
            # Add value labels on bars
            for i, bar in enumerate(bars):
                width = bar.get_width()
                if len(top_shap_values) > 0 and max(top_shap_values) > 0:
                    plt.text(width + max(top_shap_values) * 0.01, bar.get_y() + bar.get_height()/2, 
                            f'{width:.3f}', ha='left', va='center', fontsize=9)
            
            plt.tight_layout()
            
            summary_path = f'{shap_dir}/shap_summary.png'
            plt.savefig(summary_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['summary'] = f'shap-image/{analysis_id}/summary'
            print("✅ Summary plot created successfully")
            
        except Exception as e:
            print(f"⚠️ Error creating summary plot: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. Create Feature Importance Plot
        try:
            print(f"📊 Creating feature importance plot...")
            
            plt.figure(figsize=(12, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                shap_values_flat = shap_values_for_plot.flatten()
            else:
                shap_values_flat = shap_values_for_plot
            
            # Get feature names
            feature_names = list(single_df.columns)
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_values_flat))
            feature_names = feature_names[:min_length]
            shap_values_flat = shap_values_flat[:min_length]
            
            # Create DataFrame for easier handling
            feature_importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': np.abs(shap_values_flat),
                'shap_value': shap_values_flat
            }).sort_values('importance', ascending=False).head(20)
            
            # Create bar plot with colors based on positive/negative impact
            colors = ['red' if x < 0 else 'green' for x in feature_importance_df['shap_value']]
            
            plt.figure(figsize=(12, 10))
            bars = plt.barh(range(len(feature_importance_df)), 
                           feature_importance_df['shap_value'], 
                           color=colors, alpha=0.7)
            
            plt.yticks(range(len(feature_importance_df)), feature_importance_df['feature'])
            plt.xlabel('SHAP Value')
            plt.title('Feature Impact on Model Prediction\n(Red: Negative Impact, Green: Positive Impact)', 
                     fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()
            
            # Add vertical line at zero
            plt.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            
            plt.tight_layout()
            
            importance_path = f'{shap_dir}/shap_feature_importance.png'
            plt.savefig(importance_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['feature_importance'] = f'shap-image/{analysis_id}/feature_importance'
            print("✅ Feature importance plot created successfully")
            
            # Save feature importance as CSV
            feature_importance_df.to_csv(f'{shap_dir}/feature_importance.csv', index=False)
            
        except Exception as e:
            print(f"⚠️ Error creating feature importance plot: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Create Waterfall Plot
        try:
            print(f"📊 Creating waterfall plot...")
            
            plt.figure(figsize=(12, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                shap_vals = shap_values_for_plot.flatten()
            else:
                shap_vals = shap_values_for_plot
            
            # Get feature names
            feature_names = list(single_df.columns)
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_vals))
            feature_names = feature_names[:min_length]
            shap_vals = shap_vals[:min_length]
            
            # Get top 10 features by absolute value
            abs_vals = np.abs(shap_vals)
            top_indices = np.argsort(abs_vals)[-10:][::-1]
            
            top_features = [feature_names[i] for i in top_indices]
            top_shap_values = shap_vals[top_indices]
            
            # Create waterfall-style plot
            y_pos = np.arange(len(top_features))
            colors = ['red' if x < 0 else 'green' for x in top_shap_values]
            
            plt.barh(y_pos, top_shap_values, color=colors, alpha=0.7)
            plt.yticks(y_pos, top_features)
            plt.xlabel('SHAP Value Contribution')
            plt.title(f'Top 10 Feature Contributions\nBase Value: {base_value:.3f}', 
                     fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()
            
            # Add value labels
            for i, (val, color) in enumerate(zip(top_shap_values, colors)):
                if len(top_shap_values) > 0:
                    range_val = max(top_shap_values) - min(top_shap_values)
                    if range_val > 0:
                        plt.text(val + range_val * 0.01, i, 
                                f'{val:.3f}', ha='left' if val >= 0 else 'right', va='center', 
                                fontweight='bold')
            
            plt.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            plt.tight_layout()
            
            waterfall_path = f'{shap_dir}/waterfall_sample_1.png'
            plt.savefig(waterfall_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['waterfall'] = f'shap-image/{analysis_id}/waterfall'
            print("✅ Waterfall plot created successfully")
            
        except Exception as e:
            print(f"⚠️ Error creating waterfall plot: {e}")
            import traceback
            traceback.print_exc()
        
        # Close all remaining plots
        plt.close('all')
        
        print(f"✅ SHAP analysis completed for {analysis_id}")
        print(f"📊 Generated plots: {list(plot_paths.keys())}")
        
        return True, plot_paths
        
    except Exception as e:
        print(f"❌ SHAP analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        plt.close('all')
        return False, plot_paths

def align_features_with_training(processed_df, scaler):
    """Ensure features exactly match those used during training - SKIP unknown features"""
    print("🔧 Aligning features with training data...")
    
    # Get the expected feature names from the scaler
    if hasattr(scaler, 'feature_names_in_'):
        expected_features = list(scaler.feature_names_in_)
        print(f"Expected features ({len(expected_features)}): {expected_features}")
    else:
        print("⚠️ Scaler doesn't have feature_names_in_, using current features")
        return processed_df
    
    current_features = list(processed_df.columns)
    print(f"Current features ({len(current_features)}): {current_features}")
    
    # Find missing and extra features
    missing_features = set(expected_features) - set(current_features)
    extra_features = set(current_features) - set(expected_features)
    
    if missing_features:
        print(f"🔍 Adding missing features ({len(missing_features)}): {missing_features}")
        for feature in missing_features:
            processed_df[feature] = 0  # Add missing features as zeros
    
    if extra_features:
        print(f"🗑️ SKIPPING extra features ({len(extra_features)}): {extra_features}")
        # Don't include extra features in final dataframe
        processed_df = processed_df.drop(columns=list(extra_features))
    
    # Reorder columns to match training order exactly
    # Only include features that exist in expected_features
    final_features = [f for f in expected_features if f in processed_df.columns]
    
    # Add any still missing features as zeros
    for feature in expected_features:
        if feature not in processed_df.columns:
            processed_df[feature] = 0
    
    # Now reorder to match training exactly
    processed_df = processed_df[expected_features]
    
    print(f"✅ Features aligned! Final shape: {processed_df.shape}")
    print(f"Final columns: {list(processed_df.columns)}")
    
    # Verify we have exactly the right features
    if list(processed_df.columns) == expected_features:
        print("✅ Perfect feature alignment achieved!")
    else:
        print("⚠️ Feature alignment may have issues")
        print(f"Expected: {len(expected_features)} features")
        print(f"Got: {len(processed_df.columns)} features")
    
    return processed_df

def predict_with_qnn_batch(data):
    """Make predictions using your QNN model for batch processing"""
    global qnn_model, scaler, label_encoder
    
    if qnn_model is None or scaler is None or label_encoder is None:
        return None, None, "Models not loaded"
    
    try:
        # Preprocess data using the EXACT same preprocessing as training
        processed_data = preprocess_data_for_model(data)
        
        if len(processed_data) == 0:
            return None, None, "No valid data after preprocessing"
        
        print(f"📊 Processed data shape: {processed_data.shape}")
        
        # Align features with training data
        aligned_data = align_features_with_training(processed_data, scaler)
        
        print(f"📊 Aligned data shape: {aligned_data.shape}")
        
        # Scale features
        try:
            scaled_data = scaler.transform(aligned_data)
            print(f"✅ Data scaling successful")
        except Exception as scale_error:
            print(f"❌ Scaling error: {scale_error}")
            print(f"Expected features: {scaler.feature_names_in_ if hasattr(scaler, 'feature_names_in_') else 'Not available'}")
            print(f"Actual features: {list(aligned_data.columns)}")
            raise scale_error
        
        # Convert to tensor
        data_tensor = torch.tensor(scaled_data, dtype=torch.float32)
        
        # Make predictions in batches to handle large datasets
        batch_size = 1000
        all_predictions = []
        all_probabilities = []
        
        print(f"🔄 Processing {len(data_tensor)} records in batches of {batch_size}...")
        
        with torch.no_grad():
            for i in range(0, len(data_tensor), batch_size):
                batch = data_tensor[i:i+batch_size]
                outputs = qnn_model(batch)
                probabilities = F.softmax(outputs, dim=1)
                _, predicted = torch.max(outputs, 1)
                
                all_predictions.extend(predicted.numpy())
                all_probabilities.extend(probabilities.numpy())
                
                if (i // batch_size + 1) % 10 == 0:
                    print(f"   Processed {i + len(batch)}/{len(data_tensor)} records...")
        
        # Convert predictions back to labels
        predicted_labels = label_encoder.inverse_transform(all_predictions)
        all_probabilities = np.array(all_probabilities)
        
        # Debug: Print label encoder information
        print(f"🔍 Label encoder classes: {label_encoder.classes_}")
        print(f"🔍 Unique predicted indices: {np.unique(all_predictions)}")
        print(f"🔍 Unique predicted labels: {np.unique(predicted_labels)}")
        
        # Get attack probabilities
        if all_probabilities.shape[1] > 1:
            # Find which class is 'attack'
            attack_class_idx = None
            for idx, class_name in enumerate(label_encoder.classes_):
                if class_name.lower() == 'attack':
                    attack_class_idx = idx
                    break
            
            if attack_class_idx is not None:
                attack_probabilities = all_probabilities[:, attack_class_idx]
                print(f"✅ Using attack class index {attack_class_idx} for class '{label_encoder.classes_[attack_class_idx]}'")
            else:
                # Fallback: assume class 1 is attack if we have 2 classes
                if len(label_encoder.classes_) == 2:
                    attack_class_idx = 0
                    attack_probabilities = all_probabilities[:, attack_class_idx]
                    print(f"⚠️ 'attack' class not found, using index 1 (class: '{label_encoder.classes_[attack_class_idx]}')")
                else:
                    attack_class_idx = 0
                    attack_probabilities = all_probabilities[:, attack_class_idx]
                    print(f"⚠️ Multiple classes, using index 0 (class: '{label_encoder.classes_[attack_class_idx]}')")
        else:
            attack_probabilities = all_probabilities[:, 0]
            attack_class_idx = 0
            print(f"⚠️ Single class output, using index 0")
        
        # Debug: Print attack statistics
        attack_count = sum(predicted_labels == 'attack')
        normal_count = sum(predicted_labels == 'normal')
        print(f"📊 Attack predictions: {attack_count} out of {len(predicted_labels)}")
        print(f"📊 Normal predictions: {normal_count} out of {len(predicted_labels)}")
        print(f"📊 Attack probability stats: min={np.min(attack_probabilities):.3f}, max={np.max(attack_probabilities):.3f}, mean={np.mean(attack_probabilities):.3f}")
        
        # Additional debug: Check if we need to look for other attack-like labels
        if attack_count == 0:
            print("⚠️ WARNING: No 'attack' predictions found!")
            print(f"Available labels in predictions: {list(np.unique(predicted_labels))}")
            print("Checking for alternative attack labels...")
            
            # Look for alternative attack labels
            attack_like_labels = []
            for label in np.unique(predicted_labels):
                if any(keyword in label.lower() for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']):
                    attack_like_labels.append(label)
            
            if attack_like_labels:
                print(f"Found potential attack labels: {attack_like_labels}")
                # Count all attack-like predictions
                attack_count = sum(any(keyword in pred.lower() for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']) for pred in predicted_labels)
                print(f"Total attack-like predictions: {attack_count}")
        
        print(f"✅ Predictions completed: {len(predicted_labels)} records processed")
        
        return predicted_labels, attack_probabilities, None
        
    except Exception as e:
        print(f"❌ Detailed prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, f"Prediction error: {str(e)}"

def create_shap_explainer_from_data(sample_data_path=None):
    """Create a new SHAP explainer from sample data"""
    global shap_explainer, float_model, scaler
    
    if float_model is None or scaler is None:
        print("❌ Model or scaler not loaded, cannot create SHAP explainer")
        return False
    
    try:
        print("🔧 Creating new SHAP explainer...")
        
        # Define ModelWrapper class for SHAP
        class ModelWrapper:
            def __init__(self, model, scaler, feature_columns):
                self.model = model
                self.scaler = scaler
                self.feature_columns = feature_columns
                
            def __call__(self, X):
                # Convert to DataFrame if it's a numpy array
                if isinstance(X, np.ndarray):
                    X_df = pd.DataFrame(X, columns=self.feature_columns)
                else:
                    X_df = X.copy()
                
                # Scale the features
                X_scaled = self.scaler.transform(X_df)
                
                # Convert to tensor
                X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
                
                # Get predictions
                self.model.eval()
                with torch.no_grad():
                    outputs = self.model(X_tensor)
                    probabilities = F.softmax(outputs, dim=1)
                
                return probabilities.numpy()
        
        # Try to load background data from file first
        background_data = None
        background_paths = [
            'shap_results/background_data.npy',
            'background_data.npy'
        ]
        
        for bg_path in background_paths:
            if os.path.exists(bg_path):
                background_data = np.load(bg_path)
                print(f"📁 Loaded existing background data from {bg_path} (shape: {background_data.shape})")
                break
        
        # If no background data file exists, try to create from sample data
        if background_data is None:
            print("🔄 No existing background data found, trying to create from sample data...")
            
            # Try to load sample data from various paths
            sample_paths = [
                sample_data_path,
                'final.csv',
                'data/final.csv',
                '/kaggle/input/finaldataset/final.csv'
            ]
            
            for sample_path in sample_paths:
                if sample_path and os.path.exists(sample_path):
                    print(f"📁 Loading sample data from {sample_path}")
                    try:
                        sample_df = pd.read_csv(sample_path)
                        # Take a small sample for background
                        sample_size = min(100, len(sample_df))
                        background_sample = sample_df.sample(n=sample_size, random_state=42)
                        
                        # Preprocess the sample
                        processed_sample = preprocess_data_for_model(background_sample)
                        if hasattr(scaler, 'feature_names_in_'):
                            aligned_sample = align_features_with_training(processed_sample, scaler)
                            background_data = scaler.transform(aligned_sample)
                            
                            # Save for future use
                            os.makedirs('shap_results', exist_ok=True)
                            np.save('shap_results/background_data.npy', background_data)
                            print(f"💾 Background data created and saved (shape: {background_data.shape})")
                            break
                    except Exception as e:
                        print(f"⚠️ Could not process sample data from {sample_path}: {e}")
                        continue
        
        if background_data is None:
            print("❌ Could not create background data, SHAP explainer creation failed")
            return False
        
        # Create model wrapper
        if hasattr(scaler, 'feature_names_in_'):
            feature_columns = list(scaler.feature_names_in_)
        else:
            print("❌ Scaler missing feature names, cannot create SHAP explainer")
            return False
        
        model_wrapper = ModelWrapper(float_model, scaler, feature_columns)
        
        # Create SHAP explainer
        shap_explainer = shap.Explainer(model_wrapper, background_data)
        
        # Save the new explainer
        os.makedirs('shap_results', exist_ok=True)
        with open('shap_results/shap_explainer_new.pkl', 'wb') as f:
            pickle.dump(shap_explainer, f)
        
        print("✅ New SHAP explainer created and saved successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating SHAP explainer: {e}")
        return False

def send_email_alert(recipient_email, analysis_data):
    """Send email alert for high attack percentage"""
    try:
        if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
            print("⚠️ Email configuration missing")
            return False, "Email configuration missing"
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = recipient_email
        msg['Subject'] = "🚨 Security Alert: High Attack Activity Detected"
        
        body = f"""
        <html>
        <body>
        <h2 style="color: #d32f2f;">🚨 SECURITY ALERT</h2>
        <p><strong>High attack activity has been detected in your network analysis!</strong></p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #d32f2f;">
        <h3>Analysis Details:</h3>
        <ul>
        <li><strong>Analysis ID:</strong> {analysis_data['id']}</li>
        <li><strong>File:</strong> {analysis_data['filename']}</li>
        <li><strong>Total Records:</strong> {analysis_data['total_records']:,}</li>
        <li><strong>Attack Records:</strong> {analysis_data['attack_records']:,}</li>
        <li><strong>Attack Percentage:</strong> <span style="color: #d32f2f; font-weight: bold;">{analysis_data['attack_percentage']:.2f}%</span></li>
        <li><strong>Timestamp:</strong> {analysis_data['timestamp']}</li>
        </ul>
        </div>
        
        <p style="color: #d32f2f; font-weight: bold; font-size: 16px;">
        ⚠️ IMMEDIATE ACTION RECOMMENDED!
        </p>
        
        <p>Please review your network security and take appropriate measures.</p>
        
        <p>Best regards,<br>
        Security Monitoring System</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG['email'], recipient_email, text)
        server.quit()
        
        return True, "Email sent successfully"
        
    except Exception as e:
        return False, f"Email error: {str(e)}"

def format_phone_e164(phone):
    """Format Indian phone number to E.164 (+91XXXXXXXXXX)"""
    import re
    phone_digits = re.sub(r'\D', '', str(phone))
    if phone_digits.startswith('91') and len(phone_digits) == 12:
        return f'+{phone_digits}'
    elif len(phone_digits) == 10:
        return f'+91{phone_digits}'
    elif phone_digits.startswith('0') and len(phone_digits) == 11:
        return f'+91{phone_digits[1:]}'
    elif phone_digits.startswith('91') and len(phone_digits) == 13:
        return f'+{phone_digits[1:]}'
    else:
        return f'+91{phone_digits[-10:]}'

def send_sms_alert(phone_number, analysis_data):
    """Send SMS alert using Twilio"""
    try:
        if not TWILIO_CONFIG['account_sid'] or not TWILIO_CONFIG['auth_token']:
            print("⚠️ Twilio configuration missing")
            return False, "Twilio configuration missing"
        formatted_phone = format_phone_e164(phone_number)
        print(f"[SMS] Sending to {formatted_phone}")
        client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
        message_body = f"""
🚨 SECURITY ALERT 🚨
High attack activity detected!

File: {analysis_data['filename']}
Attack Rate: {analysis_data['attack_percentage']:.1f}%
Total Records: {analysis_data['total_records']:,}
Attack Records: {analysis_data['attack_records']:,}
Time: {analysis_data['timestamp']}

IMMEDIATE ACTION REQUIRED!
Check your security dashboard now.
        """
        try:
            message = client.messages.create(
                body=message_body,
                from_=TWILIO_CONFIG['phone_number'],
                to=formatted_phone
            )
            print(f"[SMS] Sent, SID: {message.sid}")
            return True, f"SMS sent: {message.sid}"
        except Exception as sms_error:
            print(f"[SMS ERROR] {sms_error}")
            return False, f"SMS error: {str(sms_error)}"
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        return False, f"SMS error: {str(e)}"

def make_voice_call(phone_number, analysis_data):
    """Make voice call alert using Twilio"""
    try:
        if not TWILIO_CONFIG['account_sid'] or not TWILIO_CONFIG['auth_token']:
            print("⚠️ Twilio configuration missing")
            return False, "Twilio configuration missing"
        formatted_phone = format_phone_e164(phone_number)
        client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
        # Short, clear message
        alert_message = (
            f"Security Alert! High attack activity detected. "
            f"File {analysis_data['filename']} shows {analysis_data['attack_percentage']:.1f} percent attack rate. "
            f"Immediate action is required. Please check your security dashboard."
        )
        # Use plain XML string, no escapes or newlines
        twiml_response = (
            f'<Response>'
            f'<Say voice="alice" rate="medium">{alert_message}</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="alice">Thank you. Goodbye.</Say>'
            f'</Response>'
        )
        print(f"[VOICE CALL] Calling {formatted_phone} with message: {alert_message}")
        call = client.calls.create(
            twiml=twiml_response,
            to=formatted_phone,
            from_=TWILIO_CONFIG['phone_number']
        )
        return True, f"Call initiated: {call.sid}"
    except Exception as e:
        print(f"[VOICE CALL ERROR] {e}")
        return False, f"Call error: {str(e)}"

def send_alerts(user_data, analysis_data):
    """Send only call and email alerts (SMS removed)"""
    alert_results = []
    def log_alert(alert_type, recipient, status):
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            INSERT INTO alert_logs (analysis_id, alert_type, recipient, status)
            VALUES (?, ?, ?, ?)
            ''', (analysis_data['id'], alert_type, recipient, status))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging alert: {e}")

    # Only call and email
    if user_data['phone']:
        print(f"📞 Making voice call to {user_data['phone']}")
        success, message = make_voice_call(user_data['phone'], analysis_data)
        alert_results.append(('Call', success, message))
        log_alert('Call', user_data['phone'], 'Success' if success else 'Failed')
        print(f"   Call result: {message}")

    if user_data['email']:
        print(f"📧 Sending email alert to {user_data['email']}")
        success, message = send_email_alert(user_data['email'], analysis_data)
        alert_results.append(('Email', success, message))
        log_alert('Email', user_data['email'], 'Success' if success else 'Failed')
        print(f"   Email result: {message}")

    return alert_results

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database/security_platform.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash FROM users WHERE username = ? AND is_active = 1', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form.get('phone', '')
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')
        
        password_hash = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            INSERT INTO users (username, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
            ''', (username, email, phone, password_hash))
            conn.commit()
            conn.close()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
# ==========================================================
# 📅 Calendly Legal / SOC Booking Route
# ==========================================================
@app.route('/book-consultation')
@login_required
def book_consultation():
    return render_template('booking.html')


@app.route('/dashboard')
@login_required
def dashboard():

    # -------------------------------
    # Database Connection
    # -------------------------------
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()

    # -------------------------------
    # Get recent analysis history
    # -------------------------------
    c.execute('''
        SELECT * FROM analysis_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''', (session['user_id'],))
    recent_analyses = c.fetchall()

    # -------------------------------
    # Get statistics
    # -------------------------------
    c.execute('''
        SELECT 
            COUNT(*) as total_analyses,
            AVG(attack_percentage) as avg_attack_rate,
            SUM(CASE WHEN attack_percentage > ? THEN 1 ELSE 0 END) as high_risk_analyses
        FROM analysis_history 
        WHERE user_id = ?
    ''', (ATTACK_THRESHOLD * 100, session['user_id']))

    stats = c.fetchone()

    # -------------------------------
    # 🔴 Get SOC Tickets
    # -------------------------------
    c.execute('''
        SELECT id, analysis_id, severity, status, created_at
        FROM soc_tickets
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))

    soc_tickets = c.fetchall()

    # -------------------------------
    # 🔴 Get open SOC incidents
    # -------------------------------
    c.execute('''
        SELECT *
        FROM soc_incidents
        WHERE user_id = ? AND status = 'OPEN'
        ORDER BY created_at DESC
    ''', (session['user_id'],))

    open_incidents = c.fetchall()

    conn.close()

    # -------------------------------
    # QR CODE GENERATION
    # -------------------------------
    ip = socket.gethostbyname(socket.gethostname())
    url = f"http://{ip}:5000/dashboard"

    qr = qrcode.make(url)

    static_folder = os.path.join(app.root_path, "static")
    os.makedirs(static_folder, exist_ok=True)

    qr_path = os.path.join(static_folder, "dashboard_qr.png")
    qr.save(qr_path)

    # -------------------------------
    # Render Dashboard
    # -------------------------------
    return render_template(
        'dashboard.html',
        recent_analyses=recent_analyses,
        stats=stats,
        model_accuracy=0.97,
        attack_threshold=ATTACK_THRESHOLD * 100,
        soc_tickets=soc_tickets,   # ✅ NOW passed correctly
        open_incidents=open_incidents,
        qr_image="dashboard_qr.png",
        url=url
    )



@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():

    if request.method == 'POST':

        # -------------------------------
        # File Validation
        # -------------------------------
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                print(f"🔄 Starting analysis for file: {filename}")

                df = pd.read_csv(filepath)
                total_records = len(df)

                predictions, probabilities, error_msg = predict_with_qnn_batch(df)

                if predictions is None:
                    flash(f'Analysis failed: {error_msg}', 'error')
                    return redirect(request.url)

                # ==========================================================
                # 🧠 ATTACK CALCULATION
                # ==========================================================
                attack_records = 0

                for pred in predictions:
                    if pred == 'attack':
                        attack_records += 1
                    elif any(keyword in str(pred).lower()
                             for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']):
                        attack_records += 1

                attack_percentage = (attack_records / total_records) * 100
                overall_prediction = "attack" if attack_percentage > (ATTACK_THRESHOLD * 100) else "normal"

                analysis_id = str(uuid.uuid4())

                # ==========================================================
                # 🔍 SHAP (Optional)
                # ==========================================================
                shap_completed = False
                plot_paths = {}

                try:
                    shap_completed, plot_paths = generate_shap_analysis(
                        df, predictions, analysis_id
                    )
                except Exception as shap_error:
                    print(f"⚠️ SHAP analysis failed: {shap_error}")

                # ==========================================================
                # 💾 SAVE ANALYSIS
                # ==========================================================
                conn = sqlite3.connect('database/security_platform.db')
                c = conn.cursor()

                c.execute('''
                    INSERT INTO analysis_history
                    (id, user_id, analysis_type, filename, total_records,
                     attack_records, attack_percentage, result, shap_analysis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_id,
                    session['user_id'],
                    'Network Traffic',
                    filename,
                    total_records,
                    attack_records,
                    attack_percentage,
                    overall_prediction,
                    shap_completed
                ))

                alert_sent = False

                # ==========================================================
                # 🚨 HIGH RISK ALERT SYSTEM (No SOC, only alerts)
                # ==========================================================
                if attack_percentage > (ATTACK_THRESHOLD * 100):

                    # Fetch user contact info
                    c.execute('SELECT email, phone FROM users WHERE id = ?',
                              (session['user_id'],))
                    user_data = c.fetchone()

                    if user_data:

                        user_alert_data = {
                            'email': user_data[0],
                            'phone': user_data[1]
                        }

                        analysis_alert_data = {
                            'id': analysis_id,
                            'filename': filename,
                            'total_records': total_records,
                            'attack_records': attack_records,
                            'attack_percentage': attack_percentage,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }

                        def alert_wrapper():
                            try:
                                send_alerts(user_alert_data, analysis_alert_data)
                            except Exception as e:
                                print(f"[ALERT THREAD ERROR] {e}")

                        threading.Thread(
                            target=alert_wrapper,
                            daemon=True
                        ).start()

                        alert_sent = True

                        c.execute(
                            'UPDATE analysis_history SET alert_sent = 1 WHERE id = ?',
                            (analysis_id,)
                        )

                    flash(
                        '🚨 HIGH ATTACK RATE DETECTED! Alerts sent to your email/phone.',
                        'warning'
                    )

                else:
                    flash(
                        f'✅ Analysis completed. Attack rate: {attack_percentage:.2f}% (Below threshold)',
                        'success'
                    )

                conn.commit()
                conn.close()

                # Remove uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)

                # ==========================================================
                # 📊 PROBABILITY STATS
                # ==========================================================
                avg_attack_prob = float(np.mean(probabilities)) if len(probabilities) > 0 else 0
                max_attack_prob = float(np.max(probabilities)) if len(probabilities) > 0 else 0
                min_attack_prob = float(np.min(probabilities)) if len(probabilities) > 0 else 0

                result_data = {
                    'analysis_id': analysis_id,
                    'total_records': total_records,
                    'attack_records': attack_records,
                    'normal_records': total_records - attack_records,
                    'attack_percentage': attack_percentage,
                    'normal_percentage': 100 - attack_percentage,
                    'overall_prediction': overall_prediction,
                    'alert_sent': alert_sent,
                    'shap_analysis': shap_completed,
                    'attack_threshold': ATTACK_THRESHOLD * 100,
                    'avg_attack_probability': avg_attack_prob,
                    'max_attack_probability': max_attack_prob,
                    'min_attack_probability': min_attack_prob,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'shap_plots': plot_paths
                }

                return render_template('results.html', result=result_data)

            except Exception as e:
                flash(f'Error analyzing file: {str(e)}', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

        else:
            flash('Invalid file type. Please upload CSV, TXT, or PCAP files.', 'error')

    return render_template('analyze.html')


def validate_indian_phone(phone):
    """Validate Indian phone number format"""
    if not phone:
        return False, "Phone number is required"
    
    # Remove all non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    
    # Check if it's a valid Indian mobile number
    # Indian mobile numbers: 10 digits starting with 6, 7, 8, or 9
    # Or with country code: +91 followed by 10 digits
    if len(phone_digits) == 10:
        if phone_digits[0] in ['6', '7', '8', '9']:
            return True, f"+91{phone_digits}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    elif len(phone_digits) == 12 and phone_digits.startswith('91'):
        if phone_digits[2] in ['6', '7', '8', '9']:
            return True, f"+{phone_digits}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    elif len(phone_digits) == 13 and phone_digits.startswith('091'):
        if phone_digits[3] in ['6', '7', '8', '9']:
            return True, f"+{phone_digits[1:]}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    else:
        return False, "Please enter a valid Indian mobile number (10 digits)"
        

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Handle profile updates
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validate phone number if provided
        if phone:
            phone_valid, phone_result = validate_indian_phone(phone)
            if not phone_valid:
                flash(f'Invalid phone number: {phone_result}', 'error')
                return redirect(request.url)
            phone = phone_result
        
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            UPDATE users SET email = ?, phone = ? WHERE id = ?
            ''', (email, phone, session['user_id']))
            conn.commit()
            conn.close()
            
            flash('Profile updated successfully!', 'success')
            return redirect(request.url)
            
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
    
    # Get user data
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('SELECT username, email, phone, created_at FROM users WHERE id = ?', (session['user_id'],))
    user_data = c.fetchone()
    conn.close()
    
    return render_template('profile.html', user=user_data)

def get_nearby_cyber_firms(latitude, longitude, security_need):
    if latitude and longitude and security_need:

        query = security_need.strip().replace(" ", "+")

        search_url = (
            f"https://www.google.com/maps/search/"
            f"{query}+cybersecurity+incident+response+company"
            f"/@{latitude},{longitude},15z"
        )

        return search_url

    return None
# -------------------------------
# 🔎 Nearby Cyber Support Route
# -------------------------------
@app.route('/cyber-support', methods=['GET', 'POST'])
@login_required
def cyber_support():

    if request.method == 'POST':
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        problem = request.form.get('problem')

        maps_url = get_nearby_cyber_firms(latitude, longitude, problem)

        if maps_url:
            return redirect(maps_url)
        else:
            flash("Unable to find nearby cyber firms.", "error")
            return redirect(url_for('dashboard'))

    return render_template('cyber_support.html')


@app.route('/analysis/<analysis_id>')
@login_required
def view_analysis(analysis_id):
    """View detailed analysis results"""
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT * FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    analysis = c.fetchone()
    
    if not analysis:
        flash('Analysis not found!', 'error')
        return redirect(url_for('dashboard'))
    
    # Get alert logs for this analysis
    c.execute('''
    SELECT alert_type, recipient, status, timestamp 
    FROM alert_logs 
    WHERE analysis_id = ?
    ORDER BY timestamp DESC
    ''', (analysis_id,))
    alerts = c.fetchall()
    
    conn.close()
    
    # Check if SHAP results exist
    shap_dir = f"shap_results/analysis_{analysis_id}"
    shap_available = os.path.exists(f"{shap_dir}/shap_summary.png")
    
    return render_template('analysis_detail.html', 
                         analysis=analysis, 
                         alerts=alerts,
                         shap_available=shap_available,
                         analysis_id=analysis_id)

@app.route('/shap/<analysis_id>')
@login_required
def view_shap(analysis_id):
    """View SHAP analysis results with all visualizations"""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT id FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    analysis = c.fetchone()
    if not analysis:
        flash('Analysis not found!', 'error')
        return redirect(url_for('dashboard'))
    
    conn.close()
    
    # Check which SHAP results exist
    shap_dir = f"shap_results/analysis_{analysis_id}"
    shap_files = {
        'summary': os.path.exists(f"{shap_dir}/shap_summary.png"),
        'feature_importance': os.path.exists(f"{shap_dir}/shap_feature_importance.png"),
        'force_plot': os.path.exists(f"{shap_dir}/force_plot.png"),
        'waterfall_plots': []
    }
    
    # Check for waterfall plots
    for i in range(1, 6):  # Check for 5 waterfall plots
        if os.path.exists(f"{shap_dir}/waterfall_sample_{i}.png"):
            shap_files['waterfall_plots'].append(i)
    
    # Load feature importance if available
    feature_importance = None
    if os.path.exists(f"{shap_dir}/feature_importance.csv"):
        try:
            feature_importance = pd.read_csv(f"{shap_dir}/feature_importance.csv").head(10)
        except:
            feature_importance = None
    
    if not any([shap_files['summary'], shap_files['feature_importance'], len(shap_files['waterfall_plots']) > 0]):
        flash('SHAP analysis not available for this analysis.', 'error')
        return redirect(url_for('view_analysis', analysis_id=analysis_id))
    
    return render_template('shap_analysis.html', 
                         analysis_id=analysis_id,
                         analysis=analysis,
                         shap_files=shap_files,
                         feature_importance=feature_importance)

@app.route('/shap-image/<analysis_id>/<image_type>')
@login_required
def serve_shap_image(analysis_id, image_type):
    """Serve SHAP analysis images, including heatmap."""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''SELECT id FROM analysis_history WHERE id = ? AND user_id = ?''', (analysis_id, session['user_id']))
    if not c.fetchone():
        return "Unauthorized", 403
    conn.close()
    shap_dir = f"shap_results/analysis_{analysis_id}"
    image_map = {
        'summary': f"{shap_dir}/shap_summary.png",
        'feature_importance': f"{shap_dir}/shap_feature_importance.png",
        'waterfall': f"{shap_dir}/waterfall_sample_1.png",
        'heatmap': f"{shap_dir}/shap_heatmap.png"
    }
    image_path = image_map.get(image_type)
    if not image_path:
        return "Invalid image type", 400
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/png')
    else:
        return "SHAP image not found", 404

@app.route('/api/shap-data/<analysis_id>')
@login_required
def get_shap_data(analysis_id):
    """Get SHAP analysis data as JSON"""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT id FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    if not c.fetchone():
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn.close()
    
    try:
        shap_dir = f"shap_results/analysis_{analysis_id}"
        
        # Load feature importance
        feature_importance = None
        if os.path.exists(f"{shap_dir}/feature_importance.csv"):
            feature_importance_df = pd.read_csv(f"{shap_dir}/feature_importance.csv")
            feature_importance = feature_importance_df.to_dict('records')
        
        # Load feature names
        feature_names = None
        if os.path.exists(f"{shap_dir}/feature_names.json"):
            import json
            with open(f"{shap_dir}/feature_names.json", 'r') as f:
                feature_names = json.load(f)
        
        # Check available visualizations
        available_plots = {
            'summary': os.path.exists(f"{shap_dir}/shap_summary.png"),
            'feature_importance': os.path.exists(f"{shap_dir}/shap_feature_importance.png"),
            'force_plot': os.path.exists(f"{shap_dir}/force_plot.png"),
            'waterfall_count': len([f for f in os.listdir(shap_dir) if f.startswith('waterfall_sample_') and f.endswith('.png')]) if os.path.exists(shap_dir) else 0
        }
        
        return jsonify({
            'status': 'success',
            'feature_importance': feature_importance,
            'feature_names': feature_names,
            'available_plots': available_plots,
            'analysis_id': analysis_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-shap-explainer', methods=['POST'])


def generate_incident_report(user, analysis_data):
    """
    Generates a Cyber Incident Report PDF
    """

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cyber Security Incident Report", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    pdf.multi_cell(0, 8, f"""
User: {user}
Incident ID: {analysis_data['id']}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

File Analyzed: {analysis_data['filename']}
Total Records: {analysis_data['total_records']}
Attack Records: {analysis_data['attack_records']}
Attack Percentage: {analysis_data['attack_percentage']}%

Risk Level: {"HIGH" if analysis_data['attack_percentage'] > 50 else "MEDIUM" if analysis_data['attack_percentage'] > 20 else "LOW"}

Model Threshold: {analysis_data['threshold']}%

Recommended Actions:
- Isolate affected systems immediately
- Block suspicious IP addresses
- Change credentials
- Run full malware scan
- Escalate to SOC if necessary
""")

    filename = f"incident_report_{analysis_data['id']}.pdf"
    pdf.output(filename)

    return filename
@app.route('/download-report/<analysis_id>')
@login_required
def download_report(analysis_id):

    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()

    c.execute("""
        SELECT id, filename, total_records, attack_records, attack_percentage
        FROM analysis_history
        WHERE id = ? AND user_id = ?
    """, (analysis_id, session['user_id']))

    row = c.fetchone()
    conn.close()

    if not row:
        flash("Report not found.", "error")
        return redirect(url_for('dashboard'))

    analysis_data = {
        "id": row[0],
        "filename": row[1],
        "total_records": row[2],
        "attack_records": row[3],
        "attack_percentage": row[4],
        "threshold": ATTACK_THRESHOLD * 100
    }

    pdf_file = generate_incident_report(session['username'], analysis_data)

    return send_file(pdf_file, as_attachment=True)

@login_required
def create_shap_explainer_api():
    """API endpoint to create a new SHAP explainer"""
    try:
        # Check if we can create SHAP explainer
        if float_model is None or scaler is None:
            return jsonify({'error': 'Model or scaler not loaded'}), 500
        
        # Try to create SHAP explainer
        success = create_shap_explainer_from_data()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'SHAP explainer created successfully',
                'shap_available': shap_explainer is not None
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create SHAP explainer'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-features', methods=['POST'])
@login_required
def debug_features():
    """Debug endpoint to check feature alignment"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Save file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'debug_' + filename)
            file.save(filepath)
            
            try:
                # Load and preprocess a small sample
                df = pd.read_csv(filepath)
                sample_df = df.head(10)  # Just take first 10 rows for debugging
                
                print(f"📊 Debug: Original data shape: {sample_df.shape}")
                print(f"📊 Debug: Original columns: {list(sample_df.columns)}")
                
                # Preprocess
                processed_data = preprocess_data_for_model(sample_df)
                print(f"📊 Debug: Processed data shape: {processed_data.shape}")
                print(f"📊 Debug: Processed columns: {list(processed_data.columns)}")
                
                # Check alignment
                if scaler and hasattr(scaler, 'feature_names_in_'):
                    expected_features = list(scaler.feature_names_in_)
                    current_features = list(processed_data.columns)
                    
                    missing_features = set(expected_features) - set(current_features)
                    extra_features = set(current_features) - set(expected_features)
                    
                    # Clean up
                    os.remove(filepath)
                    
                    return jsonify({
                        'status': 'success',
                        'original_shape': df.shape,
                        'original_columns': list(df.columns),
                        'processed_shape': processed_data.shape,
                        'processed_columns': list(processed_data.columns),
                        'expected_features_count': len(expected_features),
                        'expected_features': expected_features,
                        'missing_features': list(missing_features),
                        'extra_features': list(extra_features),
                        'features_match': len(missing_features) == 0 and len(extra_features) == 0
                    })
                else:
                    # Clean up
                    os.remove(filepath)
                    
                    return jsonify({
                        'status': 'warning',
                        'message': 'Scaler feature names not available',
                        'processed_shape': processed_data.shape,
                        'processed_columns': list(processed_data.columns)
                    })
                    
            except Exception as e:
                # Clean up
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': f'Processing error: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Invalid file type'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/model-status')
@login_required
def model_status():
    """API endpoint to check model status"""
    status_info = {
        'float_loaded': float_model is not None,
        'model_loaded': qnn_model is not None,  # Using float model for predictions
        'scaler_loaded': scaler is not None,
        'encoder_loaded': label_encoder is not None,
        'shap_loaded': shap_explainer is not None,
        'device': str(device),
        'models_directory_exists': os.path.exists('models'),
        'float_model_exists': os.path.exists('models/improved_float_model.pth'),
        'attack_threshold': ATTACK_THRESHOLD * 100,
        'shap_background_exists': os.path.exists('shap_results/background_data.npy'),
        'final_csv_available': any(os.path.exists(path) for path in [
            'final.csv', 'data/final.csv', '/kaggle/input/finaldataset/final.csv'
        ])
    }
    
    # Add feature information if scaler is loaded
    if scaler is not None:
        if hasattr(scaler, 'feature_names_in_'):
            status_info['expected_features_count'] = len(scaler.feature_names_in_)
            status_info['expected_features'] = list(scaler.feature_names_in_)
        else:
            status_info['expected_features_count'] = 'Unknown'
            status_info['expected_features'] = []
    
    # Add label encoder information
    if label_encoder is not None:
        status_info['classes'] = list(label_encoder.classes_)
        status_info['num_classes'] = len(label_encoder.classes_)
    
    # Add SHAP status
    shap_files = {
        'explainer': any(os.path.exists(path) for path in [
            'shap_results/shap_explainer.pkl',
            'shap_explainer.pkl',
            'models/shap_explainer.pkl'
        ]),
        'background_data': os.path.exists('shap_results/background_data.npy'),
        'can_create_new': float_model is not None and scaler is not None
    }
    status_info['shap_files'] = shap_files
    
    return jsonify(status_info)

@app.route('/api/test-alerts', methods=['POST'])
@login_required
def test_alerts():
    """Test alert system (for debugging)"""
    try:
        # Get user data
        conn = sqlite3.connect('database/security_platform.db')
        c = conn.cursor()
        c.execute('SELECT email, phone FROM users WHERE id = ?', (session['user_id'],))
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            return jsonify({'error': 'User data not found'}), 404
        
        # Create test analysis data
        test_analysis_data = {
            'id': 'test-' + str(uuid.uuid4())[:8],
            'filename': 'test_file.csv',
            'total_records': 1000,
            'attack_records': 350,
            'attack_percentage': 35.0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        user_alert_data = {'email': user_data[0], 'phone': user_data[1]}
        
        # Send test alerts
        alert_results = send_alerts(user_alert_data, test_analysis_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Test alerts sent',
            'results': alert_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

import requests

import requests
from flask import request, jsonify

import random

CYBER_RESPONSES = {
    "malware": [
        "Malware is malicious software designed to infiltrate or damage systems without user consent.",
        "A malware attack typically involves harmful programs that compromise data, steal information, or disrupt operations.",
        "Malware refers to software intentionally created to cause harm, including viruses, worms, and ransomware."
    ],
    "phishing": [
        "Phishing attacks trick users into revealing sensitive information through fake emails or websites.",
        "A phishing attempt usually impersonates trusted entities to steal credentials or financial data.",
        "Phishing is a social engineering tactic used to deceive users into sharing confidential information."
    ],
    "ransomware": [
        "Ransomware encrypts victim data and demands payment for restoration.",
        "A ransomware attack locks files and pressures victims into paying a ransom.",
        "Ransomware is a type of malware that restricts access until a payment is made."
    ],
    "ddos": [
        "A DDoS attack overwhelms a system with traffic, causing service disruption.",
        "Distributed Denial-of-Service attacks flood servers with excessive requests.",
        "DDoS attacks aim to make online services unavailable by overloading them."
    ]
}

GENERIC_RESPONSES = [
    "Cybersecurity threats evolve constantly. It is important to monitor network traffic, use strong authentication, and keep systems updated.",
    "Security risks can arise from vulnerabilities, misconfigurations, or malicious actors. Prevention involves layered defense strategies.",
    "Modern cyber attacks exploit human behavior and technical weaknesses. Proactive monitoring is essential.",
    "A strong cybersecurity posture includes firewalls, intrusion detection, encryption, and user awareness training."
]

@app.route("/api/chatbot", methods=["POST"])
@login_required
def chatbot_api():
    try:
        data = request.get_json()
        user_message = data.get("message", "").lower()

        if not user_message:
            return jsonify({"reply": "Please enter a message."})

        # Check for keyword match
        for keyword in CYBER_RESPONSES:
            if keyword in user_message:
                response = random.choice(CYBER_RESPONSES[keyword])
                return jsonify({"reply": response})

        # If no keyword matched, give smart generic answer
        response = random.choice(GENERIC_RESPONSES)
        return jsonify({"reply": response})

    except Exception as e:
        print("CHATBOT ERROR:", e)
        return jsonify({"reply": "⚠️ Internal assistant error."})


@app.route("/qr")
def generate_qr():
    ip = get_local_ip()
    url = f"http://{ip}:5000"

    qr = qrcode.make(url)

    qr_path = os.path.join("static", "dashboard_qr.png")
    qr.save(qr_path)

    return render_template("qr.html", qr_image="dashboard_qr.png", url=url)

@app.route('/legal-support')
@login_required
def legal_support():
    return render_template("legal_support.html")

@app.route('/payment')
@login_required
def payment():
    # UPI payment link
    upi_id = "shreenidhibalaji2004@okhdfcbank"   # ⚠️ Replace with your real UPI ID
    name = "CyberGuard AI SOC"
    amount = 499  # Service charge
    note = "SOC Incident Response Support"

    upi_link = f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR&tn={note}"

    # Generate QR
    qr = qrcode.make(upi_link)

    static_folder = os.path.join(app.root_path, "static")
    os.makedirs(static_folder, exist_ok=True)

    qr_path = os.path.join(static_folder, "upi_qr.png")
    qr.save(qr_path)

    return render_template(
        "payment.html",
        amount=amount,
        upi_id=upi_id,
        qr_image="upi_qr.png"
    )


@app.errorhandler(413)
def file_too_large(error):
    flash('File too large! Maximum size is 50MB.', 'error')
    return redirect(url_for('analyze'))

# Create .env template file
def create_env_template():
    """Create a template .env file if it doesn't exist"""
    env_template = """# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-change-this-in-production

# Email Configuration (Gmail)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_template)
        print("📝 Created .env template file. Please update it with your credentials.")


if __name__ == '__main__':
    # Create .env template
    create_env_template()
    
    # Initialize database
    init_db()
    
    # Load models at startup
    model_loaded = load_models()
    if not model_loaded:
        print("⚠️  Warning: Models not loaded. Please ensure model files are in 'models/' directory.")
        print("💡 Make sure you have:")
        print("   - models/improved_float_model.pth")
        print("   - models/improved_quantized_model.pth")
        print("   - shap_results/shap_explainer.pkl (optional)")
    
    # Verify configurations
    print("\n🔧 Configuration Status:")
    print(f"   Email configured: {'✅' if EMAIL_CONFIG['email'] and EMAIL_CONFIG['password'] else '❌'}")
    print(f"   Twilio configured: {'✅' if TWILIO_CONFIG['account_sid'] and TWILIO_CONFIG['auth_token'] else '❌'}")
    print(f"   Attack threshold: {ATTACK_THRESHOLD * 100}%")
    
    if not (EMAIL_CONFIG['email'] and EMAIL_CONFIG['password']):
        print("⚠️  Email alerts will not work. Please configure EMAIL_ADDRESS and EMAIL_PASSWORD in .env")
    
    if not (TWILIO_CONFIG['account_sid'] and TWILIO_CONFIG['auth_token']):
        print("⚠️  SMS/Call alerts will not work. Please configure Twilio credentials in .env")
    
    print(f"\n🚀 Starting Flask app on http://0.0.0.0:5000")
    print(f"📱 Indian phone number validation enabled")
    print(f"🎯 SHAP analysis integration enabled")
    print(f"🚨 Multi-channel alerts (Email/SMS/Call) enabled")
    app.run(host="0.0.0.0", port=5000, debug=True)

=======
import torch


from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

import qrcode
import socket
import os

from fpdf import FPDF
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash, session
import os
import pandas as pd
import numpy as np
import uuid
from datetime import datetime
import sqlite3
import threading
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from twilio.rest import Client
import pickle
import shap
import warnings
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt
import time

# Environment variables (create a .env file with these)
from dotenv import load_dotenv
load_dotenv()

# Import your model components
#import torch
import ipaddress
import re
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn
import torch.nn.functional as F

app = Flask(__name__)
def get_local_ip():
    return socket.gethostbyname(socket.gethostname())

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this-in-production')

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)
os.makedirs("database", exist_ok=True)
os.makedirs("models", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("shap_results", exist_ok=True)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'txt', 'pcap'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Email Configuration (from .env)
EMAIL_CONFIG = {
    'smtp_server': os.getenv('EMAIL_HOST', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('EMAIL_PORT', 587)),
    'email': os.getenv('EMAIL_ADDRESS'),
    'password': os.getenv('EMAIL_PASSWORD')
}

# Twilio Configuration (from .env)
TWILIO_CONFIG = {
    'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
    'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
    'phone_number': os.getenv('TWILIO_PHONE_NUMBER')
}

# Alert thresholds
ATTACK_THRESHOLD = 0.01 # 30% threshold for attack detection (as requested)

# Your QNN Model Classes
class ImprovedNN(nn.Module):
    def __init__(self, input_size, num_classes):
        super(ImprovedNN, self).__init__()
        
        # Layer normalization for better training stability
        self.input_norm = nn.LayerNorm(input_size)
        
        # Deeper network with residual connections
        self.fc1 = nn.Linear(input_size, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.dropout1 = nn.Dropout(0.3)
        
        self.fc2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.dropout2 = nn.Dropout(0.4)
        
        self.fc3 = nn.Linear(128, 64)
        self.bn3 = nn.BatchNorm1d(64)
        self.dropout3 = nn.Dropout(0.3)
        
        self.fc4 = nn.Linear(64, 32)
        self.bn4 = nn.BatchNorm1d(32)
        self.dropout4 = nn.Dropout(0.2)
        
        self.fc5 = nn.Linear(32, num_classes)
        
    def forward(self, x):
        # Input normalization
        x = self.input_norm(x)
        
        # Layer 1
        x1 = F.relu(self.bn1(self.fc1(x)))
        x1 = self.dropout1(x1)
        
        # Layer 2
        x2 = F.relu(self.bn2(self.fc2(x1)))
        x2 = self.dropout2(x2)
        
        # Layer 3
        x3 = F.relu(self.bn3(self.fc3(x2)))
        x3 = self.dropout3(x3)
        
        # Layer 4
        x4 = F.relu(self.bn4(self.fc4(x3)))
        x4 = self.dropout4(x4)
        
        # Output layer
        output = self.fc5(x4)
        
        return output

# Global variables for models
qnn_model = None
float_model = None
label_encoder = None
scaler = None
shap_explainer = None
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def load_models():
    """Load your trained QNN and float models"""
    global qnn_model, float_model, label_encoder, scaler, shap_explainer
    
    try:
        # Check if model files exist
        float_model_path = 'models/improved_float_model.pth'
        quant_model_path = 'models/improved_quantized_model.pth'
        
        if not os.path.exists(float_model_path):
            print(f"❌ Float model not found at {float_model_path}")
            return False
        
        # Load float model
        print("Loading float model...")
        try:
            float_checkpoint = torch.load(float_model_path, map_location='cpu', weights_only=False)
            
            # Initialize the model
            float_model = ImprovedNN(
                float_checkpoint['input_size'], 
                float_checkpoint['num_classes']
            )
            float_model.load_state_dict(float_checkpoint['model_state_dict'])
            float_model.eval()
            
            # Load preprocessing components
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                label_encoder = float_checkpoint['label_encoder']
                scaler = float_checkpoint['scaler']
            
            print("✅ Float model loaded successfully!")
            
        except Exception as e:
            print(f"❌ Error loading float model: {e}")
            return False
        
        # Try to load quantized model
        print("Loading quantized model...")
        try:
            if os.path.exists(quant_model_path):
                quant_checkpoint = torch.load(quant_model_path, map_location='cpu', weights_only=False)
                qnn_model = quant_checkpoint['model']
                print("✅ Quantized model loaded successfully!")
            else:
                print("⚠️  Quantized model not found, using float model for predictions")
                qnn_model = float_model
                
        except Exception as e:
            print(f"⚠️  Error loading quantized model: {e}")
            qnn_model = float_model
        
        # Try to load SHAP explainer
        print("Loading SHAP explainer...")
        try:
            shap_explainer_path = 'shap_results\shap_explainer.pkl'
            if os.path.exists(shap_explainer_path):
                with open(shap_explainer_path, 'rb') as f:
                    shap_explainer = pickle.load(f)
                print("✅ SHAP explainer loaded successfully!")
            else:
                print("⚠️  SHAP explainer not found, SHAP analysis will be skipped")
                
        except Exception as e:
            print(f"⚠️  Error loading SHAP explainer: {e}")
            shap_explainer = None
        
        print(f"✅ Models loaded successfully!")
        print(f"   Model input size: {float_checkpoint['input_size']}")
        print(f"   Model classes: {float_checkpoint['num_classes']}")
        print(f"   Label encoder classes: {label_encoder.classes_}")
        print(f"   Device: {device}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading models: {e}")
        return False

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )
    ''')
    
    # Create analysis history table
    c.execute('''
    CREATE TABLE IF NOT EXISTS analysis_history (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        analysis_type TEXT,
        filename TEXT,
        total_records INTEGER,
        attack_records INTEGER,
        attack_percentage REAL,
        result TEXT,
        alert_sent BOOLEAN DEFAULT 0,
        shap_analysis BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create alert logs table
    c.execute('''
    CREATE TABLE IF NOT EXISTS alert_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id TEXT,
        alert_type TEXT,
        recipient TEXT,
        status TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (analysis_id) REFERENCES analysis_history (id)
    )
    ''')

 


    conn.commit()
    conn.close()



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_address_to_numeric(address):
    """Convert IP/MAC addresses to numeric format"""
    if ':' in str(address):  # MAC address
        mac_address = re.sub(r':', '', str(address))
        try:
            return int(mac_address, 16)
        except ValueError:
            return 0
    else:  # IPv4 address
        try:
            return int(ipaddress.IPv4Address(str(address)))
        except ValueError:
            return 0

def get_training_protocol_mapping():
    """Get the exact protocol mapping used during training from final.csv"""
    try:
        # Try to load final.csv to get the exact protocol distribution used in training
        final_csv_paths = [
            'final.csv',
            'data/final.csv', 
            '../final.csv',
            '/kaggle/input/finaldataset/final.csv'  # Common Kaggle path
        ]
        
        final_df = None
        for path in final_csv_paths:
            if os.path.exists(path):
                print(f"📁 Found final.csv at: {path}")
                final_df = pd.read_csv(path)
                break
        
        if final_df is not None and 'Protocol' in final_df.columns:
            # Get the top 10 protocols from training data
            top_protocols = final_df['Protocol'].value_counts().head(10).index.tolist()
            print(f"✅ Extracted training protocols from final.csv: {top_protocols}")
            return top_protocols
        else:
            print("⚠️ Could not load final.csv, using fallback protocol list")
    except Exception as e:
        print(f"⚠️ Error loading final.csv: {e}")
    
    # Fallback: Based on common protocols seen in network traffic datasets
    return [
        'RTP', 'DISCARD', 'SIP', 'TCP', 'UDP', 
        'SSH', 'RTCP', 'STUN', 'CLASSIC-STUN', 'RTP EVENT'
    ]

def preprocess_data_for_model(df):
    """Enhanced preprocessing with EXACT match to training preprocessing using final.csv reference"""
    print(f"📊 Starting preprocessing for {len(df)} records...")
    
    # Make a copy
    processed_df = df.copy()
    
    # Handle missing values first
    print(f"Missing values before processing:\n{processed_df.isnull().sum()}")
    
    # Filter addresses with '.' or ':' (more robust)
    if 'Source' in processed_df.columns and 'Destination' in processed_df.columns:
        source_mask = processed_df['Source'].astype(str).apply(lambda x: '.' in x or ':' in x)
        dest_mask = processed_df['Destination'].astype(str).apply(lambda x: '.' in x or ':' in x)
        processed_df = processed_df[source_mask & dest_mask]
        print(f"After filtering addresses: {processed_df.shape}")
        
        # Convert addresses to numeric
        processed_df['Source'] = processed_df['Source'].apply(convert_address_to_numeric)
        processed_df['Destination'] = processed_df['Destination'].apply(convert_address_to_numeric)
        
        # Convert to float and handle any remaining issues
        processed_df['Source'] = pd.to_numeric(processed_df['Source'], errors='coerce')
        processed_df['Destination'] = pd.to_numeric(processed_df['Destination'], errors='coerce')
    
    # Drop unnecessary columns
    columns_to_drop = ['No.', 'Info', 'Unnamed: 0']
    for col in columns_to_drop:
        if col in processed_df.columns:
            processed_df = processed_df.drop(col, axis=1)
            print(f"Dropped column: {col}")
    
    # Handle Protocol column with EXACT same encoding as training (using final.csv reference)
    if 'Protocol' in processed_df.columns:
        print(f"Protocol value counts before mapping:\n{processed_df['Protocol'].value_counts()}")
        
        # Get the EXACT top 10 protocols from training
        training_top_protocols = get_training_protocol_mapping()
        print(f"Using training top protocols: {training_top_protocols}")
        
        # Map protocols: if in training top 10, keep it; otherwise map to 'Other'
        processed_df['Protocol'] = processed_df['Protocol'].apply(
            lambda x: x if x in training_top_protocols else 'Other'
        )
        
        print(f"Protocol mapping after training alignment:\n{processed_df['Protocol'].value_counts()}")
        
        # One-hot encode with EXACT same protocol names as training
        protocol_dummies = pd.get_dummies(processed_df['Protocol'], prefix='Protocol')
        processed_df = pd.concat([processed_df, protocol_dummies.astype(int)], axis=1)
        processed_df = processed_df.drop('Protocol', axis=1)
        print(f"Added {len(protocol_dummies.columns)} protocol features")
        print(f"Protocol features created: {list(protocol_dummies.columns)}")
    
    # Handle other categorical columns
    categorical_cols = processed_df.select_dtypes(include=['object']).columns
    for col in categorical_cols:
        if col != 'label':  # Don't encode target
            print(f"Encoding categorical column: {col}")
            if processed_df[col].nunique() > 20:
                # Too many categories, use frequency encoding
                freq_map = processed_df[col].value_counts().to_dict()
                processed_df[f'{col}_freq'] = processed_df[col].map(freq_map)
                processed_df = processed_df.drop(col, axis=1)
            else:
                # One-hot encode
                dummies = pd.get_dummies(processed_df[col], prefix=col)
                processed_df = pd.concat([processed_df, dummies.astype(int)], axis=1)
                processed_df = processed_df.drop(col, axis=1)
    
    # Handle infinite values first
    processed_df = processed_df.replace([np.inf, -np.inf], np.nan)
    
    # Separate numeric and non-numeric columns
    numeric_cols = processed_df.select_dtypes(include=[np.number]).columns.tolist()
    non_numeric_cols = processed_df.select_dtypes(exclude=[np.number]).columns.tolist()
    
    print(f"Numeric columns: {len(numeric_cols)}")
    print(f"Non-numeric columns: {non_numeric_cols}")
    
    # Fill NaN values only in numeric columns
    if len(numeric_cols) > 0:
        processed_df[numeric_cols] = processed_df[numeric_cols].fillna(processed_df[numeric_cols].median())
    
    # Keep only numeric columns (same as training)
    processed_df = processed_df[numeric_cols]
    
    print(f"Final preprocessed shape: {processed_df.shape}")
    print(f"Final columns: {list(processed_df.columns)}")
    
    return processed_df
def generate_shap_analysis(data, predictions, analysis_id):
    """
    Generate SHAP visualizations with robust error handling for all model types
    """
    global float_model, scaler, label_encoder
    import numpy as np
    
    shap_dir = f"shap_results/analysis_{analysis_id}"
    os.makedirs(shap_dir, exist_ok=True)
    plot_paths = {}
    
    try:
        print(f"🔄 Starting SHAP analysis for {analysis_id}...")
        
        if float_model is None or scaler is None:
            print("❌ Model or scaler not loaded, cannot perform SHAP analysis")
            return False, plot_paths
            
        # Preprocess data
        processed_data = preprocess_data_for_model(data)
        if len(processed_data) == 0:
            print("❌ No valid data after preprocessing for SHAP")
            return False, plot_paths
            
        aligned_data = align_features_with_training(processed_data, scaler)
        scaled_data = scaler.transform(aligned_data)
        
        # Use first sample for explanation
        sample_idx = 0
        single_row = scaled_data[sample_idx:sample_idx+1]
        single_df = pd.DataFrame(single_row, columns=aligned_data.columns)
        
        print(f"📊 SHAP sample shape: {single_row.shape}")
        print(f"📊 Feature count: {len(aligned_data.columns)}")
        
        def model_predict_proba(X):
            """Wrapper function for model predictions"""
            X_tensor = torch.tensor(X, dtype=torch.float32)
            float_model.eval()
            with torch.no_grad():
                outputs = float_model(X_tensor)
                probabilities = F.softmax(outputs, dim=1)
            return probabilities.numpy()
        
        # Create background data (smaller sample for faster computation)
        background_size = min(50, len(scaled_data))
        background_data = scaled_data[:background_size]
        
        print(f"📊 Background data shape: {background_data.shape}")
        
        # Create SHAP explainer
        explainer = shap.KernelExplainer(model_predict_proba, background_data)
        
        # Get SHAP values
        print("🔄 Computing SHAP values...")
        shap_values = explainer.shap_values(single_row)
        
        # Debug: Print shapes and types
        print(f"📊 SHAP values type: {type(shap_values)}")
        if isinstance(shap_values, list):
            print(f"📊 SHAP values list length: {len(shap_values)}")
            for i, sv in enumerate(shap_values):
                print(f"   Class {i} shape: {np.array(sv).shape}")
        else:
            print(f"📊 SHAP values shape: {np.array(shap_values).shape}")
        
        print(f"📊 Expected value type: {type(explainer.expected_value)}")
        print(f"📊 Expected value: {explainer.expected_value}")
        
        # Handle different SHAP value formats
        shap_array = np.array(shap_values)
        print(f"📊 SHAP array shape: {shap_array.shape}")
        
        # Get model prediction for this sample
        pred_probs = model_predict_proba(single_row)[0]
        predicted_class_idx = int(np.argmax(pred_probs))
        
        print(f"📊 Predicted class index: {predicted_class_idx}")
        print(f"📊 Prediction probabilities: {pred_probs}")
        
        if isinstance(shap_values, list):
            # Multi-class case: shap_values is a list
            num_classes = len(shap_values)
            print(f"📊 Multi-class model detected (list): {num_classes} classes")
            
            # Ensure we don't go out of bounds
            if predicted_class_idx >= len(shap_values):
                predicted_class_idx = 0
                print(f"⚠️ Adjusted predicted class index to 0")
            
            # Get SHAP values for predicted class
            shap_values_for_plot = np.array(shap_values[predicted_class_idx])
            if len(shap_values_for_plot.shape) > 1:
                shap_values_for_plot = shap_values_for_plot[0]  # Take first row if 2D
            
        elif len(shap_array.shape) == 3:
            # 3D array case: (samples, features, classes)
            print(f"📊 Multi-class model detected (3D array): {shap_array.shape[2]} classes")
            
            # Ensure we don't go out of bounds
            if predicted_class_idx >= shap_array.shape[2]:
                predicted_class_idx = 0
                print(f"⚠️ Adjusted predicted class index to 0")
            
            # Extract SHAP values for predicted class: shape (1, 15, 2) -> (15,)
            shap_values_for_plot = shap_array[0, :, predicted_class_idx]
            
        elif len(shap_array.shape) == 2:
            # 2D array case: (samples, features) - single class
            print("📊 Single class model detected (2D array)")
            shap_values_for_plot = shap_array[0]  # Take first sample
            
        else:
            # 1D array case: (features,) - single class, single sample
            print("📊 Single class model detected (1D array)")
            shap_values_for_plot = shap_array
        
        # Handle base value
        if isinstance(explainer.expected_value, np.ndarray):
            if len(explainer.expected_value) > predicted_class_idx:
                base_value = explainer.expected_value[predicted_class_idx]
            else:
                base_value = explainer.expected_value[0]
        else:
            base_value = explainer.expected_value
        
        print(f"📊 Final SHAP values shape: {shap_values_for_plot.shape}")
        print(f"📊 Base value: {base_value}")
        
        # Set dark theme for plots
        plt.style.use('dark_background')
        
        # 1. Create Summary Plot (Bar plot - most reliable)
        try:
            print(f"📊 Creating summary plot with SHAP values shape: {shap_values_for_plot.shape}")
            
            plt.figure(figsize=(10, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                print(f"⚠️ SHAP values still multi-dimensional: {shap_values_for_plot.shape}")
                shap_values_for_plot = shap_values_for_plot.flatten()
            
            # Create feature importance data
            feature_names = list(single_df.columns)
            abs_shap_values = np.abs(shap_values_for_plot)
            
            print(f"📊 Feature names length: {len(feature_names)}")
            print(f"📊 SHAP values length: {len(shap_values_for_plot)}")
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_values_for_plot))
            feature_names = feature_names[:min_length]
            abs_shap_values = abs_shap_values[:min_length]
            
            # Sort by importance
            sorted_indices = np.argsort(abs_shap_values)[::-1]
            top_n = min(15, len(sorted_indices))  # Top 15 features or less
            top_features = sorted_indices[:top_n]
            
            top_feature_names = [feature_names[i] for i in top_features]
            top_shap_values = abs_shap_values[top_features]
            
            # Create horizontal bar plot
            y_pos = np.arange(len(top_feature_names))
            bars = plt.barh(y_pos, top_shap_values, color='skyblue')
            
            plt.yticks(y_pos, top_feature_names)
            plt.xlabel('SHAP Value (Absolute)')
            plt.title('Top Feature Importance (SHAP Analysis)', fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()  # Highest importance at top
            
            # Add value labels on bars
            for i, bar in enumerate(bars):
                width = bar.get_width()
                if len(top_shap_values) > 0 and max(top_shap_values) > 0:
                    plt.text(width + max(top_shap_values) * 0.01, bar.get_y() + bar.get_height()/2, 
                            f'{width:.3f}', ha='left', va='center', fontsize=9)
            
            plt.tight_layout()
            
            summary_path = f'{shap_dir}/shap_summary.png'
            plt.savefig(summary_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['summary'] = f'shap-image/{analysis_id}/summary'
            print("✅ Summary plot created successfully")
            
        except Exception as e:
            print(f"⚠️ Error creating summary plot: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. Create Feature Importance Plot
        try:
            print(f"📊 Creating feature importance plot...")
            
            plt.figure(figsize=(12, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                shap_values_flat = shap_values_for_plot.flatten()
            else:
                shap_values_flat = shap_values_for_plot
            
            # Get feature names
            feature_names = list(single_df.columns)
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_values_flat))
            feature_names = feature_names[:min_length]
            shap_values_flat = shap_values_flat[:min_length]
            
            # Create DataFrame for easier handling
            feature_importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': np.abs(shap_values_flat),
                'shap_value': shap_values_flat
            }).sort_values('importance', ascending=False).head(20)
            
            # Create bar plot with colors based on positive/negative impact
            colors = ['red' if x < 0 else 'green' for x in feature_importance_df['shap_value']]
            
            plt.figure(figsize=(12, 10))
            bars = plt.barh(range(len(feature_importance_df)), 
                           feature_importance_df['shap_value'], 
                           color=colors, alpha=0.7)
            
            plt.yticks(range(len(feature_importance_df)), feature_importance_df['feature'])
            plt.xlabel('SHAP Value')
            plt.title('Feature Impact on Model Prediction\n(Red: Negative Impact, Green: Positive Impact)', 
                     fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()
            
            # Add vertical line at zero
            plt.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            
            plt.tight_layout()
            
            importance_path = f'{shap_dir}/shap_feature_importance.png'
            plt.savefig(importance_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['feature_importance'] = f'shap-image/{analysis_id}/feature_importance'
            print("✅ Feature importance plot created successfully")
            
            # Save feature importance as CSV
            feature_importance_df.to_csv(f'{shap_dir}/feature_importance.csv', index=False)
            
        except Exception as e:
            print(f"⚠️ Error creating feature importance plot: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Create Waterfall Plot
        try:
            print(f"📊 Creating waterfall plot...")
            
            plt.figure(figsize=(12, 8))
            
            # Ensure we have 1D array
            if len(shap_values_for_plot.shape) > 1:
                shap_vals = shap_values_for_plot.flatten()
            else:
                shap_vals = shap_values_for_plot
            
            # Get feature names
            feature_names = list(single_df.columns)
            
            # Ensure arrays match in length
            min_length = min(len(feature_names), len(shap_vals))
            feature_names = feature_names[:min_length]
            shap_vals = shap_vals[:min_length]
            
            # Get top 10 features by absolute value
            abs_vals = np.abs(shap_vals)
            top_indices = np.argsort(abs_vals)[-10:][::-1]
            
            top_features = [feature_names[i] for i in top_indices]
            top_shap_values = shap_vals[top_indices]
            
            # Create waterfall-style plot
            y_pos = np.arange(len(top_features))
            colors = ['red' if x < 0 else 'green' for x in top_shap_values]
            
            plt.barh(y_pos, top_shap_values, color=colors, alpha=0.7)
            plt.yticks(y_pos, top_features)
            plt.xlabel('SHAP Value Contribution')
            plt.title(f'Top 10 Feature Contributions\nBase Value: {base_value:.3f}', 
                     fontsize=14, fontweight='bold')
            plt.gca().invert_yaxis()
            
            # Add value labels
            for i, (val, color) in enumerate(zip(top_shap_values, colors)):
                if len(top_shap_values) > 0:
                    range_val = max(top_shap_values) - min(top_shap_values)
                    if range_val > 0:
                        plt.text(val + range_val * 0.01, i, 
                                f'{val:.3f}', ha='left' if val >= 0 else 'right', va='center', 
                                fontweight='bold')
            
            plt.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            plt.tight_layout()
            
            waterfall_path = f'{shap_dir}/waterfall_sample_1.png'
            plt.savefig(waterfall_path, dpi=150, bbox_inches='tight', facecolor='black')
            plt.close()
            
            plot_paths['waterfall'] = f'shap-image/{analysis_id}/waterfall'
            print("✅ Waterfall plot created successfully")
            
        except Exception as e:
            print(f"⚠️ Error creating waterfall plot: {e}")
            import traceback
            traceback.print_exc()
        
        # Close all remaining plots
        plt.close('all')
        
        print(f"✅ SHAP analysis completed for {analysis_id}")
        print(f"📊 Generated plots: {list(plot_paths.keys())}")
        
        return True, plot_paths
        
    except Exception as e:
        print(f"❌ SHAP analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        plt.close('all')
        return False, plot_paths

def align_features_with_training(processed_df, scaler):
    """Ensure features exactly match those used during training - SKIP unknown features"""
    print("🔧 Aligning features with training data...")
    
    # Get the expected feature names from the scaler
    if hasattr(scaler, 'feature_names_in_'):
        expected_features = list(scaler.feature_names_in_)
        print(f"Expected features ({len(expected_features)}): {expected_features}")
    else:
        print("⚠️ Scaler doesn't have feature_names_in_, using current features")
        return processed_df
    
    current_features = list(processed_df.columns)
    print(f"Current features ({len(current_features)}): {current_features}")
    
    # Find missing and extra features
    missing_features = set(expected_features) - set(current_features)
    extra_features = set(current_features) - set(expected_features)
    
    if missing_features:
        print(f"🔍 Adding missing features ({len(missing_features)}): {missing_features}")
        for feature in missing_features:
            processed_df[feature] = 0  # Add missing features as zeros
    
    if extra_features:
        print(f"🗑️ SKIPPING extra features ({len(extra_features)}): {extra_features}")
        # Don't include extra features in final dataframe
        processed_df = processed_df.drop(columns=list(extra_features))
    
    # Reorder columns to match training order exactly
    # Only include features that exist in expected_features
    final_features = [f for f in expected_features if f in processed_df.columns]
    
    # Add any still missing features as zeros
    for feature in expected_features:
        if feature not in processed_df.columns:
            processed_df[feature] = 0
    
    # Now reorder to match training exactly
    processed_df = processed_df[expected_features]
    
    print(f"✅ Features aligned! Final shape: {processed_df.shape}")
    print(f"Final columns: {list(processed_df.columns)}")
    
    # Verify we have exactly the right features
    if list(processed_df.columns) == expected_features:
        print("✅ Perfect feature alignment achieved!")
    else:
        print("⚠️ Feature alignment may have issues")
        print(f"Expected: {len(expected_features)} features")
        print(f"Got: {len(processed_df.columns)} features")
    
    return processed_df

def predict_with_qnn_batch(data):
    """Make predictions using your QNN model for batch processing"""
    global qnn_model, scaler, label_encoder
    
    if qnn_model is None or scaler is None or label_encoder is None:
        return None, None, "Models not loaded"
    
    try:
        # Preprocess data using the EXACT same preprocessing as training
        processed_data = preprocess_data_for_model(data)
        
        if len(processed_data) == 0:
            return None, None, "No valid data after preprocessing"
        
        print(f"📊 Processed data shape: {processed_data.shape}")
        
        # Align features with training data
        aligned_data = align_features_with_training(processed_data, scaler)
        
        print(f"📊 Aligned data shape: {aligned_data.shape}")
        
        # Scale features
        try:
            scaled_data = scaler.transform(aligned_data)
            print(f"✅ Data scaling successful")
        except Exception as scale_error:
            print(f"❌ Scaling error: {scale_error}")
            print(f"Expected features: {scaler.feature_names_in_ if hasattr(scaler, 'feature_names_in_') else 'Not available'}")
            print(f"Actual features: {list(aligned_data.columns)}")
            raise scale_error
        
        # Convert to tensor
        data_tensor = torch.tensor(scaled_data, dtype=torch.float32)
        
        # Make predictions in batches to handle large datasets
        batch_size = 1000
        all_predictions = []
        all_probabilities = []
        
        print(f"🔄 Processing {len(data_tensor)} records in batches of {batch_size}...")
        
        with torch.no_grad():
            for i in range(0, len(data_tensor), batch_size):
                batch = data_tensor[i:i+batch_size]
                outputs = qnn_model(batch)
                probabilities = F.softmax(outputs, dim=1)
                _, predicted = torch.max(outputs, 1)
                
                all_predictions.extend(predicted.numpy())
                all_probabilities.extend(probabilities.numpy())
                
                if (i // batch_size + 1) % 10 == 0:
                    print(f"   Processed {i + len(batch)}/{len(data_tensor)} records...")
        
        # Convert predictions back to labels
        predicted_labels = label_encoder.inverse_transform(all_predictions)
        all_probabilities = np.array(all_probabilities)
        
        # Debug: Print label encoder information
        print(f"🔍 Label encoder classes: {label_encoder.classes_}")
        print(f"🔍 Unique predicted indices: {np.unique(all_predictions)}")
        print(f"🔍 Unique predicted labels: {np.unique(predicted_labels)}")
        
        # Get attack probabilities
        if all_probabilities.shape[1] > 1:
            # Find which class is 'attack'
            attack_class_idx = None
            for idx, class_name in enumerate(label_encoder.classes_):
                if class_name.lower() == 'attack':
                    attack_class_idx = idx
                    break
            
            if attack_class_idx is not None:
                attack_probabilities = all_probabilities[:, attack_class_idx]
                print(f"✅ Using attack class index {attack_class_idx} for class '{label_encoder.classes_[attack_class_idx]}'")
            else:
                # Fallback: assume class 1 is attack if we have 2 classes
                if len(label_encoder.classes_) == 2:
                    attack_class_idx = 0
                    attack_probabilities = all_probabilities[:, attack_class_idx]
                    print(f"⚠️ 'attack' class not found, using index 1 (class: '{label_encoder.classes_[attack_class_idx]}')")
                else:
                    attack_class_idx = 0
                    attack_probabilities = all_probabilities[:, attack_class_idx]
                    print(f"⚠️ Multiple classes, using index 0 (class: '{label_encoder.classes_[attack_class_idx]}')")
        else:
            attack_probabilities = all_probabilities[:, 0]
            attack_class_idx = 0
            print(f"⚠️ Single class output, using index 0")
        
        # Debug: Print attack statistics
        attack_count = sum(predicted_labels == 'attack')
        normal_count = sum(predicted_labels == 'normal')
        print(f"📊 Attack predictions: {attack_count} out of {len(predicted_labels)}")
        print(f"📊 Normal predictions: {normal_count} out of {len(predicted_labels)}")
        print(f"📊 Attack probability stats: min={np.min(attack_probabilities):.3f}, max={np.max(attack_probabilities):.3f}, mean={np.mean(attack_probabilities):.3f}")
        
        # Additional debug: Check if we need to look for other attack-like labels
        if attack_count == 0:
            print("⚠️ WARNING: No 'attack' predictions found!")
            print(f"Available labels in predictions: {list(np.unique(predicted_labels))}")
            print("Checking for alternative attack labels...")
            
            # Look for alternative attack labels
            attack_like_labels = []
            for label in np.unique(predicted_labels):
                if any(keyword in label.lower() for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']):
                    attack_like_labels.append(label)
            
            if attack_like_labels:
                print(f"Found potential attack labels: {attack_like_labels}")
                # Count all attack-like predictions
                attack_count = sum(any(keyword in pred.lower() for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']) for pred in predicted_labels)
                print(f"Total attack-like predictions: {attack_count}")
        
        print(f"✅ Predictions completed: {len(predicted_labels)} records processed")
        
        return predicted_labels, attack_probabilities, None
        
    except Exception as e:
        print(f"❌ Detailed prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, f"Prediction error: {str(e)}"

def create_shap_explainer_from_data(sample_data_path=None):
    """Create a new SHAP explainer from sample data"""
    global shap_explainer, float_model, scaler
    
    if float_model is None or scaler is None:
        print("❌ Model or scaler not loaded, cannot create SHAP explainer")
        return False
    
    try:
        print("🔧 Creating new SHAP explainer...")
        
        # Define ModelWrapper class for SHAP
        class ModelWrapper:
            def __init__(self, model, scaler, feature_columns):
                self.model = model
                self.scaler = scaler
                self.feature_columns = feature_columns
                
            def __call__(self, X):
                # Convert to DataFrame if it's a numpy array
                if isinstance(X, np.ndarray):
                    X_df = pd.DataFrame(X, columns=self.feature_columns)
                else:
                    X_df = X.copy()
                
                # Scale the features
                X_scaled = self.scaler.transform(X_df)
                
                # Convert to tensor
                X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
                
                # Get predictions
                self.model.eval()
                with torch.no_grad():
                    outputs = self.model(X_tensor)
                    probabilities = F.softmax(outputs, dim=1)
                
                return probabilities.numpy()
        
        # Try to load background data from file first
        background_data = None
        background_paths = [
            'shap_results/background_data.npy',
            'background_data.npy'
        ]
        
        for bg_path in background_paths:
            if os.path.exists(bg_path):
                background_data = np.load(bg_path)
                print(f"📁 Loaded existing background data from {bg_path} (shape: {background_data.shape})")
                break
        
        # If no background data file exists, try to create from sample data
        if background_data is None:
            print("🔄 No existing background data found, trying to create from sample data...")
            
            # Try to load sample data from various paths
            sample_paths = [
                sample_data_path,
                'final.csv',
                'data/final.csv',
                '/kaggle/input/finaldataset/final.csv'
            ]
            
            for sample_path in sample_paths:
                if sample_path and os.path.exists(sample_path):
                    print(f"📁 Loading sample data from {sample_path}")
                    try:
                        sample_df = pd.read_csv(sample_path)
                        # Take a small sample for background
                        sample_size = min(100, len(sample_df))
                        background_sample = sample_df.sample(n=sample_size, random_state=42)
                        
                        # Preprocess the sample
                        processed_sample = preprocess_data_for_model(background_sample)
                        if hasattr(scaler, 'feature_names_in_'):
                            aligned_sample = align_features_with_training(processed_sample, scaler)
                            background_data = scaler.transform(aligned_sample)
                            
                            # Save for future use
                            os.makedirs('shap_results', exist_ok=True)
                            np.save('shap_results/background_data.npy', background_data)
                            print(f"💾 Background data created and saved (shape: {background_data.shape})")
                            break
                    except Exception as e:
                        print(f"⚠️ Could not process sample data from {sample_path}: {e}")
                        continue
        
        if background_data is None:
            print("❌ Could not create background data, SHAP explainer creation failed")
            return False
        
        # Create model wrapper
        if hasattr(scaler, 'feature_names_in_'):
            feature_columns = list(scaler.feature_names_in_)
        else:
            print("❌ Scaler missing feature names, cannot create SHAP explainer")
            return False
        
        model_wrapper = ModelWrapper(float_model, scaler, feature_columns)
        
        # Create SHAP explainer
        shap_explainer = shap.Explainer(model_wrapper, background_data)
        
        # Save the new explainer
        os.makedirs('shap_results', exist_ok=True)
        with open('shap_results/shap_explainer_new.pkl', 'wb') as f:
            pickle.dump(shap_explainer, f)
        
        print("✅ New SHAP explainer created and saved successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating SHAP explainer: {e}")
        return False

def send_email_alert(recipient_email, analysis_data):
    """Send email alert for high attack percentage"""
    try:
        if not EMAIL_CONFIG['email'] or not EMAIL_CONFIG['password']:
            print("⚠️ Email configuration missing")
            return False, "Email configuration missing"
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['email']
        msg['To'] = recipient_email
        msg['Subject'] = "🚨 Security Alert: High Attack Activity Detected"
        
        body = f"""
        <html>
        <body>
        <h2 style="color: #d32f2f;">🚨 SECURITY ALERT</h2>
        <p><strong>High attack activity has been detected in your network analysis!</strong></p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #d32f2f;">
        <h3>Analysis Details:</h3>
        <ul>
        <li><strong>Analysis ID:</strong> {analysis_data['id']}</li>
        <li><strong>File:</strong> {analysis_data['filename']}</li>
        <li><strong>Total Records:</strong> {analysis_data['total_records']:,}</li>
        <li><strong>Attack Records:</strong> {analysis_data['attack_records']:,}</li>
        <li><strong>Attack Percentage:</strong> <span style="color: #d32f2f; font-weight: bold;">{analysis_data['attack_percentage']:.2f}%</span></li>
        <li><strong>Timestamp:</strong> {analysis_data['timestamp']}</li>
        </ul>
        </div>
        
        <p style="color: #d32f2f; font-weight: bold; font-size: 16px;">
        ⚠️ IMMEDIATE ACTION RECOMMENDED!
        </p>
        
        <p>Please review your network security and take appropriate measures.</p>
        
        <p>Best regards,<br>
        Security Monitoring System</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['email'], EMAIL_CONFIG['password'])
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG['email'], recipient_email, text)
        server.quit()
        
        return True, "Email sent successfully"
        
    except Exception as e:
        return False, f"Email error: {str(e)}"

def format_phone_e164(phone):
    """Format Indian phone number to E.164 (+91XXXXXXXXXX)"""
    import re
    phone_digits = re.sub(r'\D', '', str(phone))
    if phone_digits.startswith('91') and len(phone_digits) == 12:
        return f'+{phone_digits}'
    elif len(phone_digits) == 10:
        return f'+91{phone_digits}'
    elif phone_digits.startswith('0') and len(phone_digits) == 11:
        return f'+91{phone_digits[1:]}'
    elif phone_digits.startswith('91') and len(phone_digits) == 13:
        return f'+{phone_digits[1:]}'
    else:
        return f'+91{phone_digits[-10:]}'

def send_sms_alert(phone_number, analysis_data):
    """Send SMS alert using Twilio"""
    try:
        if not TWILIO_CONFIG['account_sid'] or not TWILIO_CONFIG['auth_token']:
            print("⚠️ Twilio configuration missing")
            return False, "Twilio configuration missing"
        formatted_phone = format_phone_e164(phone_number)
        print(f"[SMS] Sending to {formatted_phone}")
        client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
        message_body = f"""
🚨 SECURITY ALERT 🚨
High attack activity detected!

File: {analysis_data['filename']}
Attack Rate: {analysis_data['attack_percentage']:.1f}%
Total Records: {analysis_data['total_records']:,}
Attack Records: {analysis_data['attack_records']:,}
Time: {analysis_data['timestamp']}

IMMEDIATE ACTION REQUIRED!
Check your security dashboard now.
        """
        try:
            message = client.messages.create(
                body=message_body,
                from_=TWILIO_CONFIG['phone_number'],
                to=formatted_phone
            )
            print(f"[SMS] Sent, SID: {message.sid}")
            return True, f"SMS sent: {message.sid}"
        except Exception as sms_error:
            print(f"[SMS ERROR] {sms_error}")
            return False, f"SMS error: {str(sms_error)}"
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        return False, f"SMS error: {str(e)}"

def make_voice_call(phone_number, analysis_data):
    """Make voice call alert using Twilio"""
    try:
        if not TWILIO_CONFIG['account_sid'] or not TWILIO_CONFIG['auth_token']:
            print("⚠️ Twilio configuration missing")
            return False, "Twilio configuration missing"
        formatted_phone = format_phone_e164(phone_number)
        client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])
        # Short, clear message
        alert_message = (
            f"Security Alert! High attack activity detected. "
            f"File {analysis_data['filename']} shows {analysis_data['attack_percentage']:.1f} percent attack rate. "
            f"Immediate action is required. Please check your security dashboard."
        )
        # Use plain XML string, no escapes or newlines
        twiml_response = (
            f'<Response>'
            f'<Say voice="alice" rate="medium">{alert_message}</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="alice">Thank you. Goodbye.</Say>'
            f'</Response>'
        )
        print(f"[VOICE CALL] Calling {formatted_phone} with message: {alert_message}")
        call = client.calls.create(
            twiml=twiml_response,
            to=formatted_phone,
            from_=TWILIO_CONFIG['phone_number']
        )
        return True, f"Call initiated: {call.sid}"
    except Exception as e:
        print(f"[VOICE CALL ERROR] {e}")
        return False, f"Call error: {str(e)}"

def send_alerts(user_data, analysis_data):
    """Send only call and email alerts (SMS removed)"""
    alert_results = []
    def log_alert(alert_type, recipient, status):
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            INSERT INTO alert_logs (analysis_id, alert_type, recipient, status)
            VALUES (?, ?, ?, ?)
            ''', (analysis_data['id'], alert_type, recipient, status))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging alert: {e}")

    # Only call and email
    if user_data['phone']:
        print(f"📞 Making voice call to {user_data['phone']}")
        success, message = make_voice_call(user_data['phone'], analysis_data)
        alert_results.append(('Call', success, message))
        log_alert('Call', user_data['phone'], 'Success' if success else 'Failed')
        print(f"   Call result: {message}")

    if user_data['email']:
        print(f"📧 Sending email alert to {user_data['email']}")
        success, message = send_email_alert(user_data['email'], analysis_data)
        alert_results.append(('Email', success, message))
        log_alert('Email', user_data['email'], 'Success' if success else 'Failed')
        print(f"   Email result: {message}")

    return alert_results

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database/security_platform.db')
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash FROM users WHERE username = ? AND is_active = 1', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form.get('phone', '')
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('signup.html')
        
        password_hash = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            INSERT INTO users (username, email, phone, password_hash)
            VALUES (?, ?, ?, ?)
            ''', (username, email, phone, password_hash))
            conn.commit()
            conn.close()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
# ==========================================================
# 📅 Calendly Legal / SOC Booking Route
# ==========================================================
@app.route('/book-consultation')
@login_required
def book_consultation():
    return render_template('booking.html')


@app.route('/dashboard')
@login_required
def dashboard():

    # -------------------------------
    # Database Connection
    # -------------------------------
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()

    # -------------------------------
    # Get recent analysis history
    # -------------------------------
    c.execute('''
        SELECT * FROM analysis_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''', (session['user_id'],))
    recent_analyses = c.fetchall()

    # -------------------------------
    # Get statistics
    # -------------------------------
    c.execute('''
        SELECT 
            COUNT(*) as total_analyses,
            AVG(attack_percentage) as avg_attack_rate,
            SUM(CASE WHEN attack_percentage > ? THEN 1 ELSE 0 END) as high_risk_analyses
        FROM analysis_history 
        WHERE user_id = ?
    ''', (ATTACK_THRESHOLD * 100, session['user_id']))

    stats = c.fetchone()

    # -------------------------------
    # 🔴 Get SOC Tickets
    # -------------------------------
    c.execute('''
        SELECT id, analysis_id, severity, status, created_at
        FROM soc_tickets
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))

    soc_tickets = c.fetchall()

    # -------------------------------
    # 🔴 Get open SOC incidents
    # -------------------------------
    c.execute('''
        SELECT *
        FROM soc_incidents
        WHERE user_id = ? AND status = 'OPEN'
        ORDER BY created_at DESC
    ''', (session['user_id'],))

    open_incidents = c.fetchall()

    conn.close()

    # -------------------------------
    # QR CODE GENERATION
    # -------------------------------
    ip = socket.gethostbyname(socket.gethostname())
    url = f"http://{ip}:5000/dashboard"

    qr = qrcode.make(url)

    static_folder = os.path.join(app.root_path, "static")
    os.makedirs(static_folder, exist_ok=True)

    qr_path = os.path.join(static_folder, "dashboard_qr.png")
    qr.save(qr_path)

    # -------------------------------
    # Render Dashboard
    # -------------------------------
    return render_template(
        'dashboard.html',
        recent_analyses=recent_analyses,
        stats=stats,
        model_accuracy=0.97,
        attack_threshold=ATTACK_THRESHOLD * 100,
        soc_tickets=soc_tickets,   # ✅ NOW passed correctly
        open_incidents=open_incidents,
        qr_image="dashboard_qr.png",
        url=url
    )



@app.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():

    if request.method == 'POST':

        # -------------------------------
        # File Validation
        # -------------------------------
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                print(f"🔄 Starting analysis for file: {filename}")

                df = pd.read_csv(filepath)
                total_records = len(df)

                predictions, probabilities, error_msg = predict_with_qnn_batch(df)

                if predictions is None:
                    flash(f'Analysis failed: {error_msg}', 'error')
                    return redirect(request.url)

                # ==========================================================
                # 🧠 ATTACK CALCULATION
                # ==========================================================
                attack_records = 0

                for pred in predictions:
                    if pred == 'attack':
                        attack_records += 1
                    elif any(keyword in str(pred).lower()
                             for keyword in ['attack', 'malicious', 'intrusion', 'threat', 'anomaly']):
                        attack_records += 1

                attack_percentage = (attack_records / total_records) * 100
                overall_prediction = "attack" if attack_percentage > (ATTACK_THRESHOLD * 100) else "normal"

                analysis_id = str(uuid.uuid4())

                # ==========================================================
                # 🔍 SHAP (Optional)
                # ==========================================================
                shap_completed = False
                plot_paths = {}

                try:
                    shap_completed, plot_paths = generate_shap_analysis(
                        df, predictions, analysis_id
                    )
                except Exception as shap_error:
                    print(f"⚠️ SHAP analysis failed: {shap_error}")

                # ==========================================================
                # 💾 SAVE ANALYSIS
                # ==========================================================
                conn = sqlite3.connect('database/security_platform.db')
                c = conn.cursor()

                c.execute('''
                    INSERT INTO analysis_history
                    (id, user_id, analysis_type, filename, total_records,
                     attack_records, attack_percentage, result, shap_analysis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_id,
                    session['user_id'],
                    'Network Traffic',
                    filename,
                    total_records,
                    attack_records,
                    attack_percentage,
                    overall_prediction,
                    shap_completed
                ))

                alert_sent = False

                # ==========================================================
                # 🚨 HIGH RISK ALERT SYSTEM (No SOC, only alerts)
                # ==========================================================
                if attack_percentage > (ATTACK_THRESHOLD * 100):

                    # Fetch user contact info
                    c.execute('SELECT email, phone FROM users WHERE id = ?',
                              (session['user_id'],))
                    user_data = c.fetchone()

                    if user_data:

                        user_alert_data = {
                            'email': user_data[0],
                            'phone': user_data[1]
                        }

                        analysis_alert_data = {
                            'id': analysis_id,
                            'filename': filename,
                            'total_records': total_records,
                            'attack_records': attack_records,
                            'attack_percentage': attack_percentage,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }

                        def alert_wrapper():
                            try:
                                send_alerts(user_alert_data, analysis_alert_data)
                            except Exception as e:
                                print(f"[ALERT THREAD ERROR] {e}")

                        threading.Thread(
                            target=alert_wrapper,
                            daemon=True
                        ).start()

                        alert_sent = True

                        c.execute(
                            'UPDATE analysis_history SET alert_sent = 1 WHERE id = ?',
                            (analysis_id,)
                        )

                    flash(
                        '🚨 HIGH ATTACK RATE DETECTED! Alerts sent to your email/phone.',
                        'warning'
                    )

                else:
                    flash(
                        f'✅ Analysis completed. Attack rate: {attack_percentage:.2f}% (Below threshold)',
                        'success'
                    )

                conn.commit()
                conn.close()

                # Remove uploaded file
                if os.path.exists(filepath):
                    os.remove(filepath)

                # ==========================================================
                # 📊 PROBABILITY STATS
                # ==========================================================
                avg_attack_prob = float(np.mean(probabilities)) if len(probabilities) > 0 else 0
                max_attack_prob = float(np.max(probabilities)) if len(probabilities) > 0 else 0
                min_attack_prob = float(np.min(probabilities)) if len(probabilities) > 0 else 0

                result_data = {
                    'analysis_id': analysis_id,
                    'total_records': total_records,
                    'attack_records': attack_records,
                    'normal_records': total_records - attack_records,
                    'attack_percentage': attack_percentage,
                    'normal_percentage': 100 - attack_percentage,
                    'overall_prediction': overall_prediction,
                    'alert_sent': alert_sent,
                    'shap_analysis': shap_completed,
                    'attack_threshold': ATTACK_THRESHOLD * 100,
                    'avg_attack_probability': avg_attack_prob,
                    'max_attack_probability': max_attack_prob,
                    'min_attack_probability': min_attack_prob,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'shap_plots': plot_paths
                }

                return render_template('results.html', result=result_data)

            except Exception as e:
                flash(f'Error analyzing file: {str(e)}', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)

        else:
            flash('Invalid file type. Please upload CSV, TXT, or PCAP files.', 'error')

    return render_template('analyze.html')


def validate_indian_phone(phone):
    """Validate Indian phone number format"""
    if not phone:
        return False, "Phone number is required"
    
    # Remove all non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    
    # Check if it's a valid Indian mobile number
    # Indian mobile numbers: 10 digits starting with 6, 7, 8, or 9
    # Or with country code: +91 followed by 10 digits
    if len(phone_digits) == 10:
        if phone_digits[0] in ['6', '7', '8', '9']:
            return True, f"+91{phone_digits}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    elif len(phone_digits) == 12 and phone_digits.startswith('91'):
        if phone_digits[2] in ['6', '7', '8', '9']:
            return True, f"+{phone_digits}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    elif len(phone_digits) == 13 and phone_digits.startswith('091'):
        if phone_digits[3] in ['6', '7', '8', '9']:
            return True, f"+{phone_digits[1:]}"
        else:
            return False, "Indian mobile numbers must start with 6, 7, 8, or 9"
    else:
        return False, "Please enter a valid Indian mobile number (10 digits)"
        

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Handle profile updates
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validate phone number if provided
        if phone:
            phone_valid, phone_result = validate_indian_phone(phone)
            if not phone_valid:
                flash(f'Invalid phone number: {phone_result}', 'error')
                return redirect(request.url)
            phone = phone_result
        
        try:
            conn = sqlite3.connect('database/security_platform.db')
            c = conn.cursor()
            c.execute('''
            UPDATE users SET email = ?, phone = ? WHERE id = ?
            ''', (email, phone, session['user_id']))
            conn.commit()
            conn.close()
            
            flash('Profile updated successfully!', 'success')
            return redirect(request.url)
            
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
    
    # Get user data
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('SELECT username, email, phone, created_at FROM users WHERE id = ?', (session['user_id'],))
    user_data = c.fetchone()
    conn.close()
    
    return render_template('profile.html', user=user_data)

def get_nearby_cyber_firms(latitude, longitude, security_need):
    if latitude and longitude and security_need:

        query = security_need.strip().replace(" ", "+")

        search_url = (
            f"https://www.google.com/maps/search/"
            f"{query}+cybersecurity+incident+response+company"
            f"/@{latitude},{longitude},15z"
        )

        return search_url

    return None
# -------------------------------
# 🔎 Nearby Cyber Support Route
# -------------------------------
@app.route('/cyber-support', methods=['GET', 'POST'])
@login_required
def cyber_support():

    if request.method == 'POST':
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        problem = request.form.get('problem')

        maps_url = get_nearby_cyber_firms(latitude, longitude, problem)

        if maps_url:
            return redirect(maps_url)
        else:
            flash("Unable to find nearby cyber firms.", "error")
            return redirect(url_for('dashboard'))

    return render_template('cyber_support.html')


@app.route('/analysis/<analysis_id>')
@login_required
def view_analysis(analysis_id):
    """View detailed analysis results"""
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT * FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    analysis = c.fetchone()
    
    if not analysis:
        flash('Analysis not found!', 'error')
        return redirect(url_for('dashboard'))
    
    # Get alert logs for this analysis
    c.execute('''
    SELECT alert_type, recipient, status, timestamp 
    FROM alert_logs 
    WHERE analysis_id = ?
    ORDER BY timestamp DESC
    ''', (analysis_id,))
    alerts = c.fetchall()
    
    conn.close()
    
    # Check if SHAP results exist
    shap_dir = f"shap_results/analysis_{analysis_id}"
    shap_available = os.path.exists(f"{shap_dir}/shap_summary.png")
    
    return render_template('analysis_detail.html', 
                         analysis=analysis, 
                         alerts=alerts,
                         shap_available=shap_available,
                         analysis_id=analysis_id)

@app.route('/shap/<analysis_id>')
@login_required
def view_shap(analysis_id):
    """View SHAP analysis results with all visualizations"""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT id FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    analysis = c.fetchone()
    if not analysis:
        flash('Analysis not found!', 'error')
        return redirect(url_for('dashboard'))
    
    conn.close()
    
    # Check which SHAP results exist
    shap_dir = f"shap_results/analysis_{analysis_id}"
    shap_files = {
        'summary': os.path.exists(f"{shap_dir}/shap_summary.png"),
        'feature_importance': os.path.exists(f"{shap_dir}/shap_feature_importance.png"),
        'force_plot': os.path.exists(f"{shap_dir}/force_plot.png"),
        'waterfall_plots': []
    }
    
    # Check for waterfall plots
    for i in range(1, 6):  # Check for 5 waterfall plots
        if os.path.exists(f"{shap_dir}/waterfall_sample_{i}.png"):
            shap_files['waterfall_plots'].append(i)
    
    # Load feature importance if available
    feature_importance = None
    if os.path.exists(f"{shap_dir}/feature_importance.csv"):
        try:
            feature_importance = pd.read_csv(f"{shap_dir}/feature_importance.csv").head(10)
        except:
            feature_importance = None
    
    if not any([shap_files['summary'], shap_files['feature_importance'], len(shap_files['waterfall_plots']) > 0]):
        flash('SHAP analysis not available for this analysis.', 'error')
        return redirect(url_for('view_analysis', analysis_id=analysis_id))
    
    return render_template('shap_analysis.html', 
                         analysis_id=analysis_id,
                         analysis=analysis,
                         shap_files=shap_files,
                         feature_importance=feature_importance)

@app.route('/shap-image/<analysis_id>/<image_type>')
@login_required
def serve_shap_image(analysis_id, image_type):
    """Serve SHAP analysis images, including heatmap."""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''SELECT id FROM analysis_history WHERE id = ? AND user_id = ?''', (analysis_id, session['user_id']))
    if not c.fetchone():
        return "Unauthorized", 403
    conn.close()
    shap_dir = f"shap_results/analysis_{analysis_id}"
    image_map = {
        'summary': f"{shap_dir}/shap_summary.png",
        'feature_importance': f"{shap_dir}/shap_feature_importance.png",
        'waterfall': f"{shap_dir}/waterfall_sample_1.png",
        'heatmap': f"{shap_dir}/shap_heatmap.png"
    }
    image_path = image_map.get(image_type)
    if not image_path:
        return "Invalid image type", 400
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/png')
    else:
        return "SHAP image not found", 404

@app.route('/api/shap-data/<analysis_id>')
@login_required
def get_shap_data(analysis_id):
    """Get SHAP analysis data as JSON"""
    # Verify user owns this analysis
    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()
    c.execute('''
    SELECT id FROM analysis_history 
    WHERE id = ? AND user_id = ?
    ''', (analysis_id, session['user_id']))
    
    if not c.fetchone():
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn.close()
    
    try:
        shap_dir = f"shap_results/analysis_{analysis_id}"
        
        # Load feature importance
        feature_importance = None
        if os.path.exists(f"{shap_dir}/feature_importance.csv"):
            feature_importance_df = pd.read_csv(f"{shap_dir}/feature_importance.csv")
            feature_importance = feature_importance_df.to_dict('records')
        
        # Load feature names
        feature_names = None
        if os.path.exists(f"{shap_dir}/feature_names.json"):
            import json
            with open(f"{shap_dir}/feature_names.json", 'r') as f:
                feature_names = json.load(f)
        
        # Check available visualizations
        available_plots = {
            'summary': os.path.exists(f"{shap_dir}/shap_summary.png"),
            'feature_importance': os.path.exists(f"{shap_dir}/shap_feature_importance.png"),
            'force_plot': os.path.exists(f"{shap_dir}/force_plot.png"),
            'waterfall_count': len([f for f in os.listdir(shap_dir) if f.startswith('waterfall_sample_') and f.endswith('.png')]) if os.path.exists(shap_dir) else 0
        }
        
        return jsonify({
            'status': 'success',
            'feature_importance': feature_importance,
            'feature_names': feature_names,
            'available_plots': available_plots,
            'analysis_id': analysis_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-shap-explainer', methods=['POST'])


def generate_incident_report(user, analysis_data):
    """
    Generates a Cyber Incident Report PDF
    """

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Cyber Security Incident Report", ln=True)

    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    pdf.multi_cell(0, 8, f"""
User: {user}
Incident ID: {analysis_data['id']}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

File Analyzed: {analysis_data['filename']}
Total Records: {analysis_data['total_records']}
Attack Records: {analysis_data['attack_records']}
Attack Percentage: {analysis_data['attack_percentage']}%

Risk Level: {"HIGH" if analysis_data['attack_percentage'] > 50 else "MEDIUM" if analysis_data['attack_percentage'] > 20 else "LOW"}

Model Threshold: {analysis_data['threshold']}%

Recommended Actions:
- Isolate affected systems immediately
- Block suspicious IP addresses
- Change credentials
- Run full malware scan
- Escalate to SOC if necessary
""")

    filename = f"incident_report_{analysis_data['id']}.pdf"
    pdf.output(filename)

    return filename
@app.route('/download-report/<analysis_id>')
@login_required
def download_report(analysis_id):

    conn = sqlite3.connect('database/security_platform.db')
    c = conn.cursor()

    c.execute("""
        SELECT id, filename, total_records, attack_records, attack_percentage
        FROM analysis_history
        WHERE id = ? AND user_id = ?
    """, (analysis_id, session['user_id']))

    row = c.fetchone()
    conn.close()

    if not row:
        flash("Report not found.", "error")
        return redirect(url_for('dashboard'))

    analysis_data = {
        "id": row[0],
        "filename": row[1],
        "total_records": row[2],
        "attack_records": row[3],
        "attack_percentage": row[4],
        "threshold": ATTACK_THRESHOLD * 100
    }

    pdf_file = generate_incident_report(session['username'], analysis_data)

    return send_file(pdf_file, as_attachment=True)

@login_required
def create_shap_explainer_api():
    """API endpoint to create a new SHAP explainer"""
    try:
        # Check if we can create SHAP explainer
        if float_model is None or scaler is None:
            return jsonify({'error': 'Model or scaler not loaded'}), 500
        
        # Try to create SHAP explainer
        success = create_shap_explainer_from_data()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'SHAP explainer created successfully',
                'shap_available': shap_explainer is not None
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create SHAP explainer'
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-features', methods=['POST'])
@login_required
def debug_features():
    """Debug endpoint to check feature alignment"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and allowed_file(file.filename):
            # Save file temporarily
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'debug_' + filename)
            file.save(filepath)
            
            try:
                # Load and preprocess a small sample
                df = pd.read_csv(filepath)
                sample_df = df.head(10)  # Just take first 10 rows for debugging
                
                print(f"📊 Debug: Original data shape: {sample_df.shape}")
                print(f"📊 Debug: Original columns: {list(sample_df.columns)}")
                
                # Preprocess
                processed_data = preprocess_data_for_model(sample_df)
                print(f"📊 Debug: Processed data shape: {processed_data.shape}")
                print(f"📊 Debug: Processed columns: {list(processed_data.columns)}")
                
                # Check alignment
                if scaler and hasattr(scaler, 'feature_names_in_'):
                    expected_features = list(scaler.feature_names_in_)
                    current_features = list(processed_data.columns)
                    
                    missing_features = set(expected_features) - set(current_features)
                    extra_features = set(current_features) - set(expected_features)
                    
                    # Clean up
                    os.remove(filepath)
                    
                    return jsonify({
                        'status': 'success',
                        'original_shape': df.shape,
                        'original_columns': list(df.columns),
                        'processed_shape': processed_data.shape,
                        'processed_columns': list(processed_data.columns),
                        'expected_features_count': len(expected_features),
                        'expected_features': expected_features,
                        'missing_features': list(missing_features),
                        'extra_features': list(extra_features),
                        'features_match': len(missing_features) == 0 and len(extra_features) == 0
                    })
                else:
                    # Clean up
                    os.remove(filepath)
                    
                    return jsonify({
                        'status': 'warning',
                        'message': 'Scaler feature names not available',
                        'processed_shape': processed_data.shape,
                        'processed_columns': list(processed_data.columns)
                    })
                    
            except Exception as e:
                # Clean up
                if os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({'error': f'Processing error: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Invalid file type'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/model-status')
@login_required
def model_status():
    """API endpoint to check model status"""
    status_info = {
        'float_loaded': float_model is not None,
        'model_loaded': qnn_model is not None,  # Using float model for predictions
        'scaler_loaded': scaler is not None,
        'encoder_loaded': label_encoder is not None,
        'shap_loaded': shap_explainer is not None,
        'device': str(device),
        'models_directory_exists': os.path.exists('models'),
        'float_model_exists': os.path.exists('models/improved_float_model.pth'),
        'attack_threshold': ATTACK_THRESHOLD * 100,
        'shap_background_exists': os.path.exists('shap_results/background_data.npy'),
        'final_csv_available': any(os.path.exists(path) for path in [
            'final.csv', 'data/final.csv', '/kaggle/input/finaldataset/final.csv'
        ])
    }
    
    # Add feature information if scaler is loaded
    if scaler is not None:
        if hasattr(scaler, 'feature_names_in_'):
            status_info['expected_features_count'] = len(scaler.feature_names_in_)
            status_info['expected_features'] = list(scaler.feature_names_in_)
        else:
            status_info['expected_features_count'] = 'Unknown'
            status_info['expected_features'] = []
    
    # Add label encoder information
    if label_encoder is not None:
        status_info['classes'] = list(label_encoder.classes_)
        status_info['num_classes'] = len(label_encoder.classes_)
    
    # Add SHAP status
    shap_files = {
        'explainer': any(os.path.exists(path) for path in [
            'shap_results/shap_explainer.pkl',
            'shap_explainer.pkl',
            'models/shap_explainer.pkl'
        ]),
        'background_data': os.path.exists('shap_results/background_data.npy'),
        'can_create_new': float_model is not None and scaler is not None
    }
    status_info['shap_files'] = shap_files
    
    return jsonify(status_info)

@app.route('/api/test-alerts', methods=['POST'])
@login_required
def test_alerts():
    """Test alert system (for debugging)"""
    try:
        # Get user data
        conn = sqlite3.connect('database/security_platform.db')
        c = conn.cursor()
        c.execute('SELECT email, phone FROM users WHERE id = ?', (session['user_id'],))
        user_data = c.fetchone()
        conn.close()
        
        if not user_data:
            return jsonify({'error': 'User data not found'}), 404
        
        # Create test analysis data
        test_analysis_data = {
            'id': 'test-' + str(uuid.uuid4())[:8],
            'filename': 'test_file.csv',
            'total_records': 1000,
            'attack_records': 350,
            'attack_percentage': 35.0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        user_alert_data = {'email': user_data[0], 'phone': user_data[1]}
        
        # Send test alerts
        alert_results = send_alerts(user_alert_data, test_analysis_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Test alerts sent',
            'results': alert_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

import requests

import requests
from flask import request, jsonify

import random

CYBER_RESPONSES = {
    "malware": [
        "Malware is malicious software designed to infiltrate or damage systems without user consent.",
        "A malware attack typically involves harmful programs that compromise data, steal information, or disrupt operations.",
        "Malware refers to software intentionally created to cause harm, including viruses, worms, and ransomware."
    ],
    "phishing": [
        "Phishing attacks trick users into revealing sensitive information through fake emails or websites.",
        "A phishing attempt usually impersonates trusted entities to steal credentials or financial data.",
        "Phishing is a social engineering tactic used to deceive users into sharing confidential information."
    ],
    "ransomware": [
        "Ransomware encrypts victim data and demands payment for restoration.",
        "A ransomware attack locks files and pressures victims into paying a ransom.",
        "Ransomware is a type of malware that restricts access until a payment is made."
    ],
    "ddos": [
        "A DDoS attack overwhelms a system with traffic, causing service disruption.",
        "Distributed Denial-of-Service attacks flood servers with excessive requests.",
        "DDoS attacks aim to make online services unavailable by overloading them."
    ]
}

GENERIC_RESPONSES = [
    "Cybersecurity threats evolve constantly. It is important to monitor network traffic, use strong authentication, and keep systems updated.",
    "Security risks can arise from vulnerabilities, misconfigurations, or malicious actors. Prevention involves layered defense strategies.",
    "Modern cyber attacks exploit human behavior and technical weaknesses. Proactive monitoring is essential.",
    "A strong cybersecurity posture includes firewalls, intrusion detection, encryption, and user awareness training."
]

@app.route("/api/chatbot", methods=["POST"])
@login_required
def chatbot_api():
    try:
        data = request.get_json()
        user_message = data.get("message", "").lower()

        if not user_message:
            return jsonify({"reply": "Please enter a message."})

        # Check for keyword match
        for keyword in CYBER_RESPONSES:
            if keyword in user_message:
                response = random.choice(CYBER_RESPONSES[keyword])
                return jsonify({"reply": response})

        # If no keyword matched, give smart generic answer
        response = random.choice(GENERIC_RESPONSES)
        return jsonify({"reply": response})

    except Exception as e:
        print("CHATBOT ERROR:", e)
        return jsonify({"reply": "⚠️ Internal assistant error."})


@app.route("/qr")
def generate_qr():
    ip = get_local_ip()
    url = f"http://{ip}:5000"

    qr = qrcode.make(url)

    qr_path = os.path.join("static", "dashboard_qr.png")
    qr.save(qr_path)

    return render_template("qr.html", qr_image="dashboard_qr.png", url=url)

@app.route('/legal-support')
@login_required
def legal_support():
    return render_template("legal_support.html")

@app.route('/payment')
@login_required
def payment():
    # UPI payment link
    upi_id = "shreenidhibalaji2004@okhdfcbank"   # ⚠️ Replace with your real UPI ID
    name = "CyberGuard AI SOC"
    amount = 499  # Service charge
    note = "SOC Incident Response Support"

    upi_link = f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR&tn={note}"

    # Generate QR
    qr = qrcode.make(upi_link)

    static_folder = os.path.join(app.root_path, "static")
    os.makedirs(static_folder, exist_ok=True)

    qr_path = os.path.join(static_folder, "upi_qr.png")
    qr.save(qr_path)

    return render_template(
        "payment.html",
        amount=amount,
        upi_id=upi_id,
        qr_image="upi_qr.png"
    )


@app.errorhandler(413)
def file_too_large(error):
    flash('File too large! Maximum size is 50MB.', 'error')
    return redirect(url_for('analyze'))

# Create .env template file
def create_env_template():
    """Create a template .env file if it doesn't exist"""
    env_template = """# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-change-this-in-production

# Email Configuration (Gmail)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=your-twilio-phone-number
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_template)
        print("📝 Created .env template file. Please update it with your credentials.")


if __name__ == '__main__':
    # Create .env template
    create_env_template()
    
    # Initialize database
    init_db()
    
    # Load models at startup
    model_loaded = load_models()
    if not model_loaded:
        print("⚠️  Warning: Models not loaded. Please ensure model files are in 'models/' directory.")
        print("💡 Make sure you have:")
        print("   - models/improved_float_model.pth")
        print("   - models/improved_quantized_model.pth")
        print("   - shap_results/shap_explainer.pkl (optional)")
    
    # Verify configurations
    print("\n🔧 Configuration Status:")
    print(f"   Email configured: {'✅' if EMAIL_CONFIG['email'] and EMAIL_CONFIG['password'] else '❌'}")
    print(f"   Twilio configured: {'✅' if TWILIO_CONFIG['account_sid'] and TWILIO_CONFIG['auth_token'] else '❌'}")
    print(f"   Attack threshold: {ATTACK_THRESHOLD * 100}%")
    
    if not (EMAIL_CONFIG['email'] and EMAIL_CONFIG['password']):
        print("⚠️  Email alerts will not work. Please configure EMAIL_ADDRESS and EMAIL_PASSWORD in .env")
    
    if not (TWILIO_CONFIG['account_sid'] and TWILIO_CONFIG['auth_token']):
        print("⚠️  SMS/Call alerts will not work. Please configure Twilio credentials in .env")
    
    print(f"\n🚀 Starting Flask app on http://0.0.0.0:5000")
    print(f"📱 Indian phone number validation enabled")
    print(f"🎯 SHAP analysis integration enabled")
    print(f"🚨 Multi-channel alerts (Email/SMS/Call) enabled")
    app.run(host="0.0.0.0", port=5000, debug=True)

>>>>>>> 6ed5a0610661de02d4c9fa8781a0f9e0d1287d6c
