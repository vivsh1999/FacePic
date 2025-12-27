import { MongoClient } from 'mongodb'

const MONGODB_URI = process.env.MONGODB_URI || ''
const MONGODB_DATABASE = process.env.MONGODB_DATABASE || 'facepic'

let dbClient: MongoClient | null = null
let db: any = null

export const getDb = async () => {
  if (db) return db
  if (!MONGODB_URI) throw new Error('MONGODB_URI not configured')
  
  if (!dbClient) {
    dbClient = new MongoClient(MONGODB_URI)
    await dbClient.connect()
    console.log(`Connected to MongoDB: ${MONGODB_DATABASE}`)
  }
  
  db = dbClient.db(MONGODB_DATABASE)
  return db
}
