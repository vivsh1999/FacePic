import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import numpy as np

# Add processor to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock face_recognition before importing process_images
sys.modules['face_recognition'] = MagicMock()

from process_images import process_pending_images, find_matching_person

class TestImageProcessing(unittest.TestCase):
    def setUp(self):
        # Mock MongoDB
        self.mock_mongo_client = MagicMock()
        self.mock_db = self.mock_mongo_client.imagetag
        
        # Mock S3/R2
        self.mock_s3 = MagicMock()
        
        # Patch the global variables in process_images
        patcher_mongo = patch('process_images.db', self.mock_db)
        patcher_s3 = patch('process_images.s3', self.mock_s3)
        
        self.mock_db_instance = patcher_mongo.start()
        self.mock_s3_instance = patcher_s3.start()
        
        self.addCleanup(patcher_mongo.stop)
        self.addCleanup(patcher_s3.stop)

    def test_find_matching_person_match(self):
        # Setup known person with encoding
        known_encoding = np.array([0.1, 0.1, 0.1])
        test_encoding = np.array([0.11, 0.11, 0.11]) # Close enough
        
        self.mock_db.persons.find.return_value = [{"_id": "person1"}]
        self.mock_db.faces.find.return_value = [{"encoding": known_encoding.tolist()}]
        
        # Mock face_recognition.face_distance
        # It returns an array of distances
        sys.modules['face_recognition'].face_distance.return_value = np.array([0.01])
        
        result = find_matching_person(test_encoding)
        self.assertEqual(result, "person1")

    def test_find_matching_person_no_match(self):
        # Setup known person with encoding
        known_encoding = np.array([0.1, 0.1, 0.1])
        test_encoding = np.array([0.9, 0.9, 0.9]) # Far away
        
        self.mock_db.persons.find.return_value = [{"_id": "person1"}]
        self.mock_db.faces.find.return_value = [{"encoding": known_encoding.tolist()}]
        
        # Mock face_recognition.face_distance
        sys.modules['face_recognition'].face_distance.return_value = np.array([0.8])
        
        result = find_matching_person(test_encoding)
        self.assertIsNone(result)

    @patch('process_images.get_face_encodings')
    @patch('process_images.create_thumbnail')
    def test_process_pending_images_flow(self, mock_thumbnail, mock_get_encodings):
        # Setup pending image
        image_doc = {
            "_id": "img1",
            "filename": "test.jpg",
            "content_type": "image/jpeg",
            "processed": False
        }
        self.mock_db.images.find.return_value = [image_doc]
        
        # Mock face detection results
        mock_get_encodings.return_value = (
            [(10, 20, 30, 40)], # locations
            [np.array([0.1, 0.2])] # encodings
        )
        
        # Mock thumbnail creation
        mock_thumbnail.return_value = MagicMock()
        
        # Mock person matching (no match -> create new)
        self.mock_db.persons.find.return_value = []
        self.mock_db.persons.insert_one.return_value.inserted_id = "new_person_id"
        
        # Run processing
        process_pending_images()
        
        # Verify S3 download
        self.mock_s3.download_fileobj.assert_called_with('facepic', 'test.jpg', unittest.mock.ANY)
        
        # Verify DB updates
        # 1. New person created
        self.mock_db.persons.insert_one.assert_called()
        
        # 2. Face saved
        self.mock_db.faces.insert_one.assert_called()
        call_args = self.mock_db.faces.insert_one.call_args[0][0]
        self.assertEqual(call_args['image_id'], "img1")
        self.assertEqual(call_args['person_id'], "new_person_id")
        
        # 3. Thumbnail uploaded
        self.mock_s3.upload_fileobj.assert_called()
        
        # 4. Image marked processed
        self.mock_db.images.update_one.assert_called_with(
            {"_id": "img1"},
            {"$set": {"processed": True, "thumbnail_url": "thumb_test.jpg", "processed_at": unittest.mock.ANY}}
        )

if __name__ == '__main__':
    unittest.main()
