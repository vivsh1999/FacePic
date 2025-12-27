import axios from 'axios';
import type {
  Image,
  ImageDetail,
  Person,
  PersonDetail,
  PersonPhotosResponse,
  UploadResponse,
  ProcessingResponse,
  ProcessingStatus,
  Stats,
  BackgroundProcessingResponse,
  TaskStatusResponse,
  UploadAndProcessResponse,
} from '../types';

export type { TaskStatusResponse, UploadAndProcessResponse };

const api = axios.create({
  baseURL: '/api',
});

// ============ Images API ============

/**
 * Upload images and start background processing on the server.
 */
export const uploadAndProcess = async (
  files: File[]
): Promise<UploadAndProcessResponse> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await api.post<UploadAndProcessResponse>(
    '/images/upload-and-process',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
        ...getAdminHeaders(),
      },
    }
  );
  return response.data;
};

/**
 * Upload images directly to R2 via presigned URLs.
 * 1. Get presigned URL from Worker
 * 2. Upload file to R2
 * 3. Register metadata in DB via Worker
 */
export const uploadImages = async (files: File[]): Promise<UploadResponse> => {
  const uploadedImages: Image[] = [];
  const errors: string[] = [];

  for (const file of files) {
    try {
      // 1. Get Presigned URL
      const { data: { url } } = await api.post<{ url: string }>('/images/upload-url', {
        filename: file.name,
        contentType: file.type
      }, {
        headers: getAdminHeaders(),
      });

      // 2. Upload to R2
      await axios.put(url, file, {
        headers: { 'Content-Type': file.type }
      });

      // 3. Register Metadata
      const { data: { id } } = await api.post<{ id: string }>('/images/meta', {
        filename: file.name,
        original_filename: file.name,
        content_type: file.type,
        size: file.size,
        processed: false, // Will be processed by local script
        created_at: new Date().toISOString()
      }, {
        headers: getAdminHeaders(),
      });

      uploadedImages.push({
        id,
        filename: file.name,
        url: URL.createObjectURL(file), // Temporary local URL
        processed: false
      } as any);

    } catch (err: any) {
      console.error(`Failed to upload ${file.name}:`, err);
      errors.push(file.name);
    }
  }

  return {
    uploaded: uploadedImages.length,
    failed: errors.length,
    images: uploadedImages,
    errors
  };
};


export const getImages = async (
  skip = 0,
  limit = 50,
  processed?: number
): Promise<Image[]> => {
  const params: Record<string, unknown> = { skip, limit };
  if (processed !== undefined) {
    params.processed = processed;
  }
  const response = await api.get<Image[]>('/images', { params });
  return response.data;
};

export const getImage = async (imageId: string): Promise<ImageDetail> => {
  const response = await api.get<ImageDetail>(`/images/${imageId}`);
  return response.data;
};

export const deleteImage = async (imageId: string): Promise<void> => {
  await api.delete(`/images/${imageId}`, {
    headers: getAdminHeaders(),
  });
};

export const getProcessingStatus = async (): Promise<ProcessingStatus> => {
  const response = await api.get<ProcessingStatus>('/images/status');
  return response.data;
};

export const processImages = async (
  imageIds?: string[]
): Promise<ProcessingResponse> => {
  const response = await api.post<ProcessingResponse>('/images/process', {
    image_ids: imageIds,
  }, {
    headers: getAdminHeaders(),
  });
  return response.data;
};

export const processImagesBackground = async (
  imageIds?: string[]
): Promise<BackgroundProcessingResponse> => {
  const response = await api.post<BackgroundProcessingResponse>(
    '/images/process/background',
    { image_ids: imageIds },
    {
      headers: getAdminHeaders(),
    }
  );
  return response.data;
};

export const getTaskStatus = async (
  taskId: string
): Promise<TaskStatusResponse> => {
  const response = await api.get<TaskStatusResponse>(
    `/images/process/status/${taskId}`
  );
  return response.data;
};

export interface DetectedFaceInfo {
  face_id: string;
  thumbnail_url: string;
  person_id: string;
  person_name: string | null;
  is_new_person: boolean;
  image_id: string;
}

export interface UploadWithFacesResponse {
  uploaded: number;
  failed: number;
  images: Image[];
  faces_detected: number;
  persons_created: number;
  detected_faces: DetectedFaceInfo[];
  errors: string[];
}

// ============ Persons API ============

export const getPersons = async (
  skip = 0,
  limit = 50,
  labeled?: boolean,
  search?: string
): Promise<Person[]> => {
  const params: Record<string, unknown> = { skip, limit };
  if (labeled !== undefined) {
    params.labeled = labeled;
  }
  if (search) {
    params.search = search;
  }
  const response = await api.get<Person[]>('/persons', { params });
  return response.data;
};

export const getPerson = async (personId: string): Promise<PersonDetail> => {
  const response = await api.get<PersonDetail>(`/persons/${personId}`);
  return response.data;
};

export const updatePerson = async (
  personId: string,
  name: string
): Promise<Person> => {
  const response = await api.put<Person>(`/persons/${personId}`, { name }, {
    headers: getAdminHeaders(),
  });
  return response.data;
};

export const deletePerson = async (personId: string): Promise<void> => {
  await api.delete(`/persons/${personId}`, {
    headers: getAdminHeaders(),
  });
};

export const getPersonPhotos = async (
  personId: string,
  skip = 0,
  limit = 50
): Promise<PersonPhotosResponse> => {
  const response = await api.get<PersonPhotosResponse>(
    `/persons/${personId}/photos`,
    { params: { skip, limit } }
  );
  return response.data;
};

export const mergePersons = async (
  sourcePersonId: string,
  targetPersonId: string
): Promise<{ message: string; person: Person }> => {
  const response = await api.post<{ message: string; person: Person }>(
    '/persons/merge',
    {
      source_person_id: sourcePersonId,
      target_person_id: targetPersonId,
    },
    {
      headers: getAdminHeaders(),
    }
  );
  return response.data;
};

// ============ Duplicates API ============

export interface DuplicateImage {
  id: string;
  filename: string;
  original_filename: string;
  thumbnail_url: string | null;
  file_size: number | null;
  uploaded_at: string;
}

export interface DuplicateGroup {
  hash: string;
  images: DuplicateImage[];
}

export interface DuplicatesResponse {
  total_groups: number;
  total_duplicates: number;
  groups: DuplicateGroup[];
}

export interface DeleteDuplicatesResponse {
  deleted: number;
  errors: string[];
}

const getAdminHeaders = () => {
  const password = localStorage.getItem('adminPassword');
  return password ? { 'X-Admin-Password': password } : {};
};

export const getDuplicates = async (): Promise<DuplicatesResponse> => {
  const response = await api.get<DuplicatesResponse>('/images/duplicates', {
    headers: getAdminHeaders(),
  });
  return response.data;
};

export const deleteDuplicates = async (
  imageIds: string[]
): Promise<DeleteDuplicatesResponse> => {
  const response = await api.post<DeleteDuplicatesResponse>(
    '/images/duplicates/delete',
    { image_ids: imageIds },
    {
      headers: getAdminHeaders(),
    }
  );
  return response.data;
};

// ============ Stats API ============

export const getStats = async (): Promise<Stats> => {
  const response = await api.get<Stats>('/stats', {
    headers: getAdminHeaders(),
  });
  return response.data;
};

export const verifyAdmin = async (password: string): Promise<{ success: boolean; message?: string }> => {
  const response = await api.post<{ success: boolean; message?: string }>('/admin/verify', { password });
  return response.data;
};

export interface FileItem {
  name: string;
  path: string;
  is_directory: boolean;
  size?: number;
  modified_at?: number;
  processed?: boolean;
  thumbnail_path?: string;
}

export interface ListFilesOptions {
  sort?: 'name' | 'size' | 'date';
  order?: 'asc' | 'desc';
  filter?: string;
  type?: 'all' | 'files' | 'folders';
}

export const listFiles = async (path = '', options: ListFilesOptions = {}): Promise<FileItem[]> => {
  const response = await api.get<FileItem[]>('/filesystem/list', {
    params: { path, ...options },
    headers: getAdminHeaders(),
  });
  return response.data;
};

export default api;
