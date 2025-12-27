import { Hono } from 'hono'
import { ObjectId } from 'mongodb'
import { GetObjectCommand, PutObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3'
import { getSignedUrl } from '@aws-sdk/s3-request-presigner'
import { getDb } from '../db'
import { s3Client, R2_BUCKET_NAME } from '../storage'
import { adminAuth } from '../middleware/auth'

const images = new Hono()

// Helper to convert ImageDocument to response
const imageToResponse = (image: any, faceCount: number = 0) => {
  return {
    id: image._id.toString(),
    filename: image.filename,
    original_filename: image.original_filename,
    thumbnail_url: image.thumbnail_path ? `/api/images/${image._id.toString()}/thumbnail` : null,
    image_url: `/api/images/${image._id.toString()}/file`,
    width: image.width,
    height: image.height,
    file_size: image.file_size,
    uploaded_at: image.uploaded_at,
    processed: image.processed,
    face_count: faceCount,
    faces: image.faces || [],
  }
}

// List images
images.get('/', async (c) => {
  const db = await getDb()
  const skip = parseInt(c.req.query('skip') || '0')
  const limit = parseInt(c.req.query('limit') || '50')
  const processed = c.req.query('processed')
  
  const query: any = {}
  if (processed !== undefined) {
    query.processed = parseInt(processed)
  }
  
  const docs = await db.collection('images')
    .find(query)
    .sort({ uploaded_at: -1 })
    .skip(skip)
    .limit(limit)
    .toArray()
  
  const result = []
  for (const doc of docs) {
    const faceCount = await db.collection('faces').countDocuments({ image_id: doc._id.toString() })
    result.push(imageToResponse(doc, faceCount))
  }
  
  return c.json(result)
})

// Get processing status
images.get('/status', async (c) => {
  const db = await getDb()
  
  const total = await db.collection('images').countDocuments({})
  const processed = await db.collection('images').countDocuments({ processed: 1 })
  const pending = await db.collection('images').countDocuments({ processed: 0 })
  const failed = await db.collection('images').countDocuments({ processed: -1 })
  const totalFaces = await db.collection('faces').countDocuments({})
  
  return c.json({
    total_images: total,
    processed,
    pending,
    failed,
    total_faces_detected: totalFaces,
  })
})

// Get image file (redirect to R2)
images.get('/:id/file', async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid image ID' }, 400)
  }
  
  const image = await db.collection('images').findOne({ _id: new ObjectId(id) })
  if (!image) {
    return c.json({ error: 'Image not found' }, 404)
  }
  
  // If image has a filepath (local), we might not be able to serve it if we don't have access.
  // But if we assume R2 migration, we check if it's in R2.
  // The processor saves to local disk.
  // If the backend is running in a container without access to that disk, this will fail if we try to read local file.
  // However, if the user wants to migrate to Hono + R2, we should assume images are in R2 or we serve from R2.
  // For now, let's assume the filename is the key in R2.
  
  const key = image.filename
  const command = new GetObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
  })
  
  try {
    const url = await getSignedUrl(s3Client, command, { expiresIn: 3600 })
    return c.redirect(url)
  } catch (e) {
    console.error('Error generating signed URL:', e)
    return c.json({ error: 'Failed to generate URL' }, 500)
  }
})

// Get image thumbnail (redirect to R2)
images.get('/:id/thumbnail', async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid image ID' }, 400)
  }
  
  const image = await db.collection('images').findOne({ _id: new ObjectId(id) })
  if (!image || !image.thumbnail_path) {
    return c.json({ error: 'Thumbnail not found' }, 404)
  }
  
  // Assuming thumbnail_path is relative or just filename.
  // In processor, it's a full path or relative path.
  // We need to extract the filename or key.
  // If it's stored as "thumbnails/images/xyz.jpg", we use that as key.
  
  let key = image.thumbnail_path
  // If it's an absolute path, try to make it relative or extract filename
  if (key.startsWith('/')) {
    const parts = key.split('/')
    key = parts[parts.length - 1]
  }
  
  const command = new GetObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
  })
  
  try {
    const url = await getSignedUrl(s3Client, command, { expiresIn: 3600 })
    return c.redirect(url)
  } catch (e) {
    console.error('Error generating signed URL:', e)
    return c.json({ error: 'Failed to generate URL' }, 500)
  }
})

// Get face thumbnail (redirect to R2)
images.get('/faces/:faceId/thumbnail', async (c) => {
  const db = await getDb()
  const faceId = c.req.param('faceId')
  
  if (!ObjectId.isValid(faceId)) {
    return c.json({ error: 'Invalid face ID' }, 400)
  }
  
  const face = await db.collection('faces').findOne({ _id: new ObjectId(faceId) })
  if (!face || !face.thumbnail_path) {
    return c.json({ error: 'Face thumbnail not found' }, 404)
  }
  
  let key = face.thumbnail_path
  if (key.startsWith('/')) {
    const parts = key.split('/')
    key = `faces/${parts[parts.length - 1]}`
  }
  
  const command = new GetObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
  })
  
  try {
    const url = await getSignedUrl(s3Client, command, { expiresIn: 3600 })
    return c.redirect(url)
  } catch (e) {
    console.error('Error generating signed URL:', e)
    return c.json({ error: 'Failed to generate URL' }, 500)
  }
})

// Upload image
images.post('/upload', adminAuth, async (c) => {
  const db = await getDb()
  const body = await c.req.parseBody()
  const file = body['files'] // Hono handles file uploads in parseBody
  
  if (!file) {
    return c.json({ error: 'No file uploaded' }, 400)
  }
  
  const files = Array.isArray(file) ? file : [file]
  const uploaded = []
  const errors = []
  
  for (const f of files) {
    if (!(f instanceof File)) continue
    
    try {
      const buffer = await f.arrayBuffer()
      const uniqueFilename = `${Date.now()}-${f.name}`
      const key = `uploads/${uniqueFilename}`
      
      // Upload to R2
      await s3Client.send(new PutObjectCommand({
        Bucket: R2_BUCKET_NAME,
        Key: key,
        Body: Buffer.from(buffer),
        ContentType: f.type,
      }))
      
      // Create DB entry
      const imageDoc = {
        filename: uniqueFilename,
        original_filename: f.name,
        filepath: key, // Store R2 key as filepath
        thumbnail_path: null, // Thumbnail will be generated by processor
        width: 0, // Will be updated by processor
        height: 0,
        file_size: f.size,
        mime_type: f.type,
        processed: 0, // Pending
        uploaded_at: new Date(),
        faces: [],
      }
      
      const result = await db.collection('images').insertOne(imageDoc)
      
      uploaded.push(imageToResponse({ ...imageDoc, _id: result.insertedId }))
    } catch (e: any) {
      errors.push(`Failed to upload ${f.name}: ${e.message}`)
    }
  }
  
  return c.json({
    uploaded: uploaded.length,
    failed: errors.length,
    images: uploaded,
    errors,
  })
})

// Find duplicates
images.get('/duplicates', adminAuth, async (c) => {
  // Placeholder for duplicates logic
  // The python implementation calculates hashes.
  // If we don't have hashes in DB, we can't find duplicates easily without processing.
  // We'll return empty for now as per previous index.ts
  return c.json({
    total_groups: 0,
    total_duplicates: 0,
    groups: []
  })
})

// Delete duplicates
images.post('/duplicates/delete', adminAuth, async (c) => {
  const db = await getDb()
  const { image_ids } = await c.req.json()
  
  if (!Array.isArray(image_ids) || image_ids.length === 0) {
    return c.json({ deleted: 0, errors: ['No image IDs provided'] })
  }
  
  let deleted = 0
  const errors = []
  
  for (const id of image_ids) {
    if (!ObjectId.isValid(id)) {
      errors.push(`Invalid ID: ${id}`)
      continue
    }
    
    const image = await db.collection('images').findOne({ _id: new ObjectId(id) })
    if (!image) {
      errors.push(`Image not found: ${id}`)
      continue
    }
    
    try {
      // Delete from R2
      if (image.filename) {
        await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: image.filename }))
      }
      if (image.thumbnail_path) {
        let key = image.thumbnail_path
        if (key.startsWith('/')) {
          const parts = key.split('/')
          key = `thumbnails/images/${parts[parts.length - 1]}`
        }
        await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key }))
      }
      
      // Delete faces and their thumbnails
      const faces = await db.collection('faces').find({ image_id: id }).toArray()
      for (const face of faces) {
        if (face.thumbnail_path) {
          let key = face.thumbnail_path
          if (key.startsWith('/')) {
            const parts = key.split('/')
            key = `thumbnails/faces/${parts[parts.length - 1]}`
          }
          await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key }))
        }
      }
      
      await db.collection('faces').deleteMany({ image_id: id })
      await db.collection('images').deleteOne({ _id: new ObjectId(id) })
      deleted++
    } catch (e: any) {
      errors.push(`Failed to delete ${id}: ${e.message}`)
    }
  }
  
  return c.json({ deleted, errors })
})

// Delete image
images.delete('/:id', adminAuth, async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid image ID' }, 400)
  }
  
  const image = await db.collection('images').findOne({ _id: new ObjectId(id) })
  if (!image) {
    return c.json({ error: 'Image not found' }, 404)
  }
  
  // Delete from R2
  if (image.filename) {
    await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: image.filename }))
  }
  if (image.thumbnail_path) {
    // Handle thumbnail path cleanup
    let key = image.thumbnail_path
    if (key.startsWith('/')) {
      const parts = key.split('/')
      key = `thumbnails/images/${parts[parts.length - 1]}`
    }
    await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key }))
  }
  
  // Delete faces and their thumbnails
  const faces = await db.collection('faces').find({ image_id: id }).toArray()
  for (const face of faces) {
    if (face.thumbnail_path) {
      let key = face.thumbnail_path
      if (key.startsWith('/')) {
        const parts = key.split('/')
        key = `thumbnails/faces/${parts[parts.length - 1]}`
      }
      await s3Client.send(new DeleteObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key }))
    }
  }
  
  await db.collection('faces').deleteMany({ image_id: id })
  await db.collection('images').deleteOne({ _id: new ObjectId(id) })
  
  return c.json({ success: true })
})

// Get upload URL
images.post('/upload-url', adminAuth, async (c) => {
  try {
    const body = await c.req.json()
    const { filename, contentType } = body

    if (!filename || !contentType) {
      return c.json({ error: 'Missing filename or contentType' }, 400)
    }

    const command = new PutObjectCommand({
      Bucket: R2_BUCKET_NAME,
      Key: filename,
      ContentType: contentType,
    })

    const url = await getSignedUrl(s3Client, command, { expiresIn: 3600 })

    return c.json({ url })
  } catch (error: any) {
    return c.json({ error: error.message }, 500)
  }
})

// Create image meta
images.post('/meta', adminAuth, async (c) => {
  try {
    const body = await c.req.json()
    const db = await getDb()
    
    const result = await db.collection('images').insertOne({
      ...body,
      uploaded_at: new Date(),
      processed: 0
    })

    return c.json({ success: true, id: result.insertedId })
  } catch (error: any) {
    return c.json({ error: error.message }, 500)
  }
})

export default images
