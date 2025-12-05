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
} from '../types';

const api = axios.create({
  baseURL: '/api',
});

// ============ Images API ============

export const uploadImages = async (files: File[]): Promise<UploadResponse> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await api.post<UploadResponse>('/images/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
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

export const getImage = async (imageId: number): Promise<ImageDetail> => {
  const response = await api.get<ImageDetail>(`/images/${imageId}`);
  return response.data;
};

export const deleteImage = async (imageId: number): Promise<void> => {
  await api.delete(`/images/${imageId}`);
};

export const getProcessingStatus = async (): Promise<ProcessingStatus> => {
  const response = await api.get<ProcessingStatus>('/images/status');
  return response.data;
};

export const processImages = async (
  imageIds?: number[]
): Promise<ProcessingResponse> => {
  const response = await api.post<ProcessingResponse>('/images/process', {
    image_ids: imageIds,
  });
  return response.data;
};

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

export const getPerson = async (personId: number): Promise<PersonDetail> => {
  const response = await api.get<PersonDetail>(`/persons/${personId}`);
  return response.data;
};

export const updatePerson = async (
  personId: number,
  name: string
): Promise<Person> => {
  const response = await api.put<Person>(`/persons/${personId}`, { name });
  return response.data;
};

export const deletePerson = async (personId: number): Promise<void> => {
  await api.delete(`/persons/${personId}`);
};

export const getPersonPhotos = async (
  personId: number,
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
  sourcePersonId: number,
  targetPersonId: number
): Promise<{ message: string; person: Person }> => {
  const response = await api.post<{ message: string; person: Person }>(
    '/persons/merge',
    {
      source_person_id: sourcePersonId,
      target_person_id: targetPersonId,
    }
  );
  return response.data;
};

// ============ Stats API ============

export const getStats = async (): Promise<Stats> => {
  const response = await api.get<Stats>('/stats');
  return response.data;
};

export default api;
