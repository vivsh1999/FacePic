// API Types

export interface BoundingBox {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface Face {
  id: number;
  image_id: number;
  person_id: number | null;
  bbox: BoundingBox;
  thumbnail_url: string | null;
  created_at: string;
}

export interface Image {
  id: number;
  filename: string;
  original_filename: string;
  thumbnail_url: string | null;
  image_url: string;
  width: number | null;
  height: number | null;
  file_size: number | null;
  uploaded_at: string;
  processed: number;
  face_count: number;
}

export interface ImageDetail extends Image {
  faces: Face[];
}

export interface Person {
  id: number;
  name: string | null;
  display_name: string;
  face_count: number;
  photo_count: number;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface PersonDetail extends Person {
  faces: Face[];
}

export interface PersonPhoto {
  id: number;
  filename: string;
  original_filename: string;
  thumbnail_url: string | null;
  image_url: string;
  width: number | null;
  height: number | null;
  uploaded_at: string;
  faces: { id: number; bbox: BoundingBox }[];
}

export interface PersonPhotosResponse {
  person: Person;
  total_photos: number;
  photos: PersonPhoto[];
}

export interface UploadResponse {
  uploaded: number;
  failed: number;
  images: Image[];
  errors: string[];
}

export interface ProcessingResponse {
  processed: number;
  faces_detected: number;
  persons_created: number;
  errors: string[];
}

export interface ProcessingStatus {
  total_images: number;
  processed: number;
  pending: number;
  failed: number;
  total_faces_detected: number;
}

export interface BackgroundProcessingResponse {
  message: string;
  task_id: string;
  image_count: number;
}

export interface TaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  total: number;
  processed: number;
  faces_detected: number;
  persons_created: number;
  errors: string[];
  completed_at: string | null;
}

export interface Stats {
  total_images: number;
  total_faces: number;
  total_persons: number;
  labeled_persons: number;
  unlabeled_persons: number;
}
