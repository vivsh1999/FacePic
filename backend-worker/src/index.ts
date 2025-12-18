import { Hono } from 'hono'
import { cors } from 'hono/cors'
import mongoose from 'mongoose'
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3'
import { getSignedUrl } from '@aws-sdk/s3-request-presigner'

type Bindings = {
  MONGODB_URI: string
  R2_BUCKET: R2Bucket
  R2_ACCESS_KEY_ID: string
  R2_SECRET_ACCESS_KEY: string
  R2_ACCOUNT_ID: string
  R2_BUCKET_NAME: string
}

const app = new Hono<{ Bindings: Bindings }>()

app.use('/*', cors())

app.get('/', (c) => {
  return c.text('FacePic Worker')
})

// Generate a presigned URL for uploading to R2
// Note: We use the AWS SDK here because the R2Bucket binding does not support generating presigned URLs directly.
app.post('/images/upload-url', async (c) => {
  try {
    const body = await c.req.json()
    const { filename, contentType } = body

    if (!filename || !contentType) {
      return c.json({ error: 'Missing filename or contentType' }, 400)
    }

    // Ensure required env vars are present
    if (!c.env.R2_ACCESS_KEY_ID || !c.env.R2_SECRET_ACCESS_KEY || !c.env.R2_ACCOUNT_ID) {
      return c.json({ error: 'R2 credentials not configured' }, 500)
    }

    const S3 = new S3Client({
      region: 'auto',
      endpoint: `https://${c.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
      credentials: {
        accessKeyId: c.env.R2_ACCESS_KEY_ID,
        secretAccessKey: c.env.R2_SECRET_ACCESS_KEY,
      },
    })

    const command = new PutObjectCommand({
      Bucket: c.env.R2_BUCKET_NAME || 'facepic',
      Key: filename,
      ContentType: contentType,
    })

    // URL expires in 1 hour
    const url = await getSignedUrl(S3, command, { expiresIn: 3600 })

    return c.json({ url })
  } catch (error: any) {
    return c.json({ error: error.message }, 500)
  }
})

// Mongoose Schema
const ImageSchema = new mongoose.Schema({
  filename: String,
  metadata: Object,
  encodings: [Number], // Face encodings
  createdAt: { type: Date, default: Date.now }
})

// Helper to get or create model
const getImageModel = () => {
  if (mongoose.models.Image) return mongoose.model('Image');
  return mongoose.model('Image', ImageSchema);
}

app.post('/images/meta', async (c) => {
  try {
    const body = await c.req.json()
    
    if (mongoose.connection.readyState === 0) {
      await mongoose.connect(c.env.MONGODB_URI)
    }

    const Image = getImageModel()
    const newImage = new Image(body)
    await newImage.save()

    return c.json({ success: true, id: newImage._id })
  } catch (error: any) {
    return c.json({ error: error.message }, 500)
  }
})

export default app
