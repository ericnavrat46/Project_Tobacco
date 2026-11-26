import os
import sys

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import GlobalAveragePooling2D, BatchNormalization, Dropout, Dense
from tensorflow.keras.models import Model

# Inisialisasi arsitektur persis seperti di ai/train.py
base_model = MobileNetV2(
    weights=None,
    include_top=False,
    input_shape=(224, 224, 3)
)

x = base_model.output
x = GlobalAveragePooling2D(name='global_average_pooling')(x)
x = BatchNormalization()(x)
x = Dropout(0.3)(x)
x = Dense(128, activation='relu', name='feature_dense')(x)
x = Dropout(0.2)(x)
predictions = Dense(3, activation='softmax', name='quality_prediction')(x)

model = Model(inputs=base_model.input, outputs=predictions)

print("\n" + "=" * 70)
print(" ARSITEKTUR MODEL KLASIFIKASI MUTU TEMBAKAU (TobaccoGuard AI)")
print("=" * 70)
model.summary()
print("=" * 70)
