const { MongoClient } = require('mongodb');

const uri = "mongodb+srv://sharmavivek2231999_db_user:1st0nGD0n0OPHj7B@maincluster.eijmfi6.mongodb.net/facepic";

async function testConnection() {
  try {
    console.log('Attempting to connect...');
    const client = new MongoClient(uri);
    await client.connect();
    console.log('Successfully connected to MongoDB!');
    
    const db = client.db('facepic');
    const images = await db.collection('images').find({}).limit(3).toArray();
    
    console.log('Sample images:');
    images.forEach(img => {
      console.log({
        id: img._id,
        filename: img.filename,
        thumbnail_path: img.thumbnail_path,
        is_uploaded: img.is_uploaded
      });
    });

    const faces = await db.collection('faces').find({}).limit(3).toArray();
    console.log('Sample faces:');
    faces.forEach(face => {
      console.log({
        id: face._id,
        person_id: face.person_id,
        thumbnail_path: face.thumbnail_path
      });
    });

    await client.close();
  } catch (error) {
    console.error('Connection failed:', error);
  }
}

testConnection();
