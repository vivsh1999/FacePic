import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { S3Client, ListObjectsV2Command, PutObjectCommand } from '@aws-sdk/client-s3'
import { getSignedUrl } from '@aws-sdk/s3-request-presigner'
import { ObjectId } from 'mongodb'
import { getDb } from './db'
import { s3Client, R2_BUCKET_NAME } from './storage'
import images from './routes/images'
import persons from './routes/persons'
import { adminAuth, ADMIN_PASSWORD } from './middleware/auth'

const app = new Hono()

app.use('/*', cors())

app.get('/', (c) => {
  return c.text('FacePic Backend (Bun + Cloud Run)')
})

app.route('/api/images', images)
app.route('/api/persons', persons)

app.post('/api/admin/verify', async (c) => {
  const { password } = await c.req.json()
  if (password === ADMIN_PASSWORD) {
    return c.json({ success: true })
  }
  return c.json({ success: false }, 401)
})

app.get('/api/filesystem/list', async (c) => {
  const pathParam = c.req.query('path') || ''
  
  // Sorting and filtering options
  const sort = c.req.query('sort') || 'name' // name, size, date
  const order = c.req.query('order') || 'asc' // asc, desc
  const filter = c.req.query('filter') || ''
  const type = c.req.query('type') || 'all' // all, files, folders
  
  try {
    const db = await getDb()
    let currentFolderId: ObjectId | null = null
    let currentFolderIdStr: string | null = null

    if (pathParam) {
      // Ensure path starts with / for DB lookup
      const lookupPath = pathParam.startsWith('/') ? pathParam : `/${pathParam}`
      const folder = await db.collection('folders').findOne({ path: lookupPath })
      
      if (!folder) {
        // Folder not found in DB
        return c.json([])
      }
      currentFolderId = folder._id
      currentFolderIdStr = folder._id.toString()
    }

    // Query Folders (parent_id is ObjectId or null)
    const folders = await db.collection('folders').find({ 
      parent_id: currentFolderId 
    }).toArray()

    // Query Images (folder_id is String or null)
    // Note: In the processor, folder_id is stored as a string representation of ObjectId
    const images = await db.collection('images').find({ 
      folder_id: currentFolderIdStr 
    }).toArray()

    let items: any[] = [
      ...folders.map((f: any) => ({
        name: f.name,
        // Remove leading slash for frontend consistency
        path: f.path.startsWith('/') ? f.path.slice(1) : f.path,
        is_directory: true,
        size: 0,
        modified_at: f.updated_at ? new Date(f.updated_at).getTime() / 1000 : 0,
      })),
      ...images.map((i: any) => ({
        name: i.original_filename,
        // Construct path: folder path + filename
        path: pathParam ? `${pathParam}/${i.original_filename}` : i.original_filename,
        is_directory: false,
        size: i.file_size,
        modified_at: i.uploaded_at ? new Date(i.uploaded_at).getTime() / 1000 : 0,
        processed: i.processed, // Include processed status
        thumbnail_path: i.thumbnail_path
      }))
    ]

    // Apply type filter
    if (type === 'files') {
      items = items.filter(i => !i.is_directory)
    } else if (type === 'folders') {
      items = items.filter(i => i.is_directory)
    }

    // Apply name filter
    if (filter) {
      const lowerFilter = filter.toLowerCase()
      items = items.filter(i => i.name?.toLowerCase().includes(lowerFilter))
    }

    // Apply sorting
    items.sort((a, b) => {
      // Always put folders first
      if (a.is_directory && !b.is_directory) return -1
      if (!a.is_directory && b.is_directory) return 1

      let comparison = 0
      switch (sort) {
        case 'size':
          comparison = (a.size || 0) - (b.size || 0)
          break
        case 'date':
          comparison = (a.modified_at || 0) - (b.modified_at || 0)
          break
        case 'name':
        default:
          comparison = (a.name || '').localeCompare(b.name || '')
          break
      }
      return order === 'desc' ? -comparison : comparison
    })
    
    return c.json(items)
  } catch (error: any) {
    console.error('Filesystem list error:', error)
    return c.json({ error: error.message }, 500)
  }
})

app.get('/api/stats', async (c) => {
  try {
    const database = await getDb()
    const images = database.collection('images')
    const faces = database.collection('faces')
    const persons = database.collection('persons')
    
    const totalImages = await images.countDocuments()
    const totalFaces = await faces.countDocuments()
    const totalPersons = await persons.countDocuments()
    const labeledPersons = await persons.countDocuments({ name: { $ne: null } })
    
    return c.json({
      total_images: totalImages,
      total_faces: totalFaces,
      total_persons: totalPersons,
      labeled_persons: labeledPersons,
      unlabeled_persons: totalPersons - labeledPersons,
    })
  } catch (error: any) {
    return c.json({ error: error.message }, 500)
  }
})

export default {
  port: process.env.PORT || 8080,
  fetch: app.fetch,
  idleTimeout: 60, // Increase timeout to 60 seconds
}
