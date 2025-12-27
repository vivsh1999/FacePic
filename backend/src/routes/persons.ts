import { Hono } from 'hono'
import { ObjectId } from 'mongodb'
import { getDb } from '../db'
import { adminAuth } from '../middleware/auth'

const persons = new Hono()

// Helper to convert PersonDocument to response
const personToResponse = async (person: any, db: any) => {
  const faces = await db.collection('faces').find({ person_id: person._id.toString() }).toArray()
  
  const faceCount = faces.length
  const photoCount = new Set(faces.map((f: any) => f.image_id)).size
  
  let thumbnailUrl = null
  if (person.representative_face_id) {
    const face = await db.collection('faces').findOne({ _id: new ObjectId(person.representative_face_id) })
    if (face && face.thumbnail_path) {
      thumbnailUrl = `/api/images/faces/${person.representative_face_id}/thumbnail`
    }
  } else if (faces.length > 0) {
    const firstFace = faces[0]
    if (firstFace.thumbnail_path) {
      thumbnailUrl = `/api/images/faces/${firstFace._id.toString()}/thumbnail`
    }
  }
  
  return {
    id: person._id.toString(),
    name: person.name,
    display_name: person.display_name, // Assuming this exists in DB or model
    face_count: faceCount,
    photo_count: photoCount,
    thumbnail_url: thumbnailUrl,
    created_at: person.created_at,
    updated_at: person.updated_at,
  }
}

// List persons
persons.get('/', async (c) => {
  const db = await getDb()
  const skip = parseInt(c.req.query('skip') || '0')
  const limit = parseInt(c.req.query('limit') || '50')
  const labeled = c.req.query('labeled')
  const search = c.req.query('search')
  
  const query: any = {}
  
  if (labeled === 'true') {
    query.name = { $ne: null }
  } else if (labeled === 'false') {
    query.name = null
  }
  
  if (search) {
    query.name = { $regex: search, $options: 'i' }
  }
  
  const pipeline = [
    { $match: query },
    {
      $addFields: {
        has_name: { $cond: [{ $ifNull: ["$name", false] }, 1, 0] }
      }
    },
    { $sort: { has_name: -1, created_at: -1 } },
    { $skip: skip },
    { $limit: limit }
  ]
  
  const docs = await db.collection('persons').aggregate(pipeline).toArray()
  
  const result = []
  for (const doc of docs) {
    result.push(await personToResponse(doc, db))
  }
  
  return c.json(result)
})

// Get person details
persons.get('/:id', async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid person ID' }, 400)
  }
  
  const doc = await db.collection('persons').findOne({ _id: new ObjectId(id) })
  if (!doc) {
    return c.json({ error: 'Person not found' }, 404)
  }
  
  const response: any = await personToResponse(doc, db)
  
  const faces = await db.collection('faces').find({ person_id: id }).toArray()
  
  response.faces = faces.map((face: any) => ({
    id: face._id.toString(),
    bbox: {
      top: face.bbox_top,
      right: face.bbox_right,
      bottom: face.bbox_bottom,
      left: face.bbox_left,
    },
    thumbnail_url: face.thumbnail_path ? `/api/images/faces/${face._id.toString()}/thumbnail` : null,
    person_id: face.person_id,
    image_id: face.image_id,
    created_at: face.created_at,
  }))
  
  return c.json(response)
})

// Update person
persons.put('/:id', adminAuth, async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  const body = await c.req.json()
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid person ID' }, 400)
  }
  
  const doc = await db.collection('persons').findOne({ _id: new ObjectId(id) })
  if (!doc) {
    return c.json({ error: 'Person not found' }, 404)
  }
  
  const name = body.name && body.name.trim() ? body.name.trim() : null
  
  await db.collection('persons').updateOne(
    { _id: new ObjectId(id) },
    { $set: { name, updated_at: new Date() } }
  )
  
  const updatedDoc = await db.collection('persons').findOne({ _id: new ObjectId(id) })
  return c.json(await personToResponse(updatedDoc, db))
})

// Delete person
persons.delete('/:id', adminAuth, async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid person ID' }, 400)
  }
  
  const doc = await db.collection('persons').findOne({ _id: new ObjectId(id) })
  if (!doc) {
    return c.json({ error: 'Person not found' }, 404)
  }
  
  // Unassign faces
  await db.collection('faces').updateMany(
    { person_id: id },
    { $set: { person_id: null } }
  )
  
  await db.collection('persons').deleteOne({ _id: new ObjectId(id) })
  
  return c.json({ message: 'Person deleted successfully' })
})

// Get person photos
persons.get('/:id/photos', async (c) => {
  const db = await getDb()
  const id = c.req.param('id')
  const skip = parseInt(c.req.query('skip') || '0')
  const limit = parseInt(c.req.query('limit') || '50')
  
  if (!ObjectId.isValid(id)) {
    return c.json({ error: 'Invalid person ID' }, 400)
  }
  
  const doc = await db.collection('persons').findOne({ _id: new ObjectId(id) })
  if (!doc) {
    return c.json({ error: 'Person not found' }, 404)
  }
  
  const faces = await db.collection('faces').find({ person_id: id }).toArray()
  const imageIds = [...new Set(faces.map((f: any) => f.image_id))]
  const totalPhotos = imageIds.length
  
  const paginatedIds = imageIds.slice(skip, skip + limit)
  const objectIds = paginatedIds.map((id: string) => new ObjectId(id))
  
  const images = await db.collection('images').find({ _id: { $in: objectIds } }).toArray()
  
  // Sort by uploaded_at desc
  images.sort((a: any, b: any) => {
    const dateA = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0
    const dateB = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0
    return dateB - dateA
  })
  
  const photos = images.map((image: any) => {
    const personFaces = faces.filter((f: any) => f.image_id === image._id.toString())
    
    return {
      id: image._id.toString(),
      filename: image.filename,
      original_filename: image.original_filename,
      thumbnail_url: image.thumbnail_path ? `/api/images/${image._id.toString()}/thumbnail` : null,
      image_url: `/api/images/${image._id.toString()}/file`,
      width: image.width,
      height: image.height,
      uploaded_at: image.uploaded_at,
      faces: personFaces.map((face: any) => ({
        id: face._id.toString(),
        bbox: {
          top: face.bbox_top,
          right: face.bbox_right,
          bottom: face.bbox_bottom,
          left: face.bbox_left,
        }
      }))
    }
  })
  
  return c.json({
    person: await personToResponse(doc, db),
    total_photos: totalPhotos,
    photos
  })
})

// Merge persons
persons.post('/merge', adminAuth, async (c) => {
  const db = await getDb()
  const body = await c.req.json()
  const { source_person_id, target_person_id } = body
  
  if (source_person_id === target_person_id) {
    return c.json({ error: 'Source and target person IDs must be different' }, 400)
  }
  
  const sourcePerson = await db.collection('persons').findOne({ _id: new ObjectId(source_person_id) })
  const targetPerson = await db.collection('persons').findOne({ _id: new ObjectId(target_person_id) })
  
  if (!sourcePerson || !targetPerson) {
    return c.json({ error: 'One or both persons not found' }, 404)
  }
  
  // Move faces from source to target
  await db.collection('faces').updateMany(
    { person_id: source_person_id },
    { $set: { person_id: target_person_id } }
  )
  
  // Delete source person
  await db.collection('persons').deleteOne({ _id: new ObjectId(source_person_id) })
  
  // Update target person timestamp
  await db.collection('persons').updateOne(
    { _id: new ObjectId(target_person_id) },
    { $set: { updated_at: new Date() } }
  )
  
  const updatedTarget = await db.collection('persons').findOne({ _id: new ObjectId(target_person_id) })
  
  return c.json({
    message: 'Persons merged successfully',
    person: await personToResponse(updatedTarget, db)
  })
})

export default persons
