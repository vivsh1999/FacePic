import ImageUpload from '../components/ImageUpload';

export default function UploadPage() {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Upload Photos</h1>
        <p className="text-slate-600">
          Upload your photos and we'll automatically detect and group faces.
        </p>
      </div>

      <ImageUpload />
    </div>
  );
}
