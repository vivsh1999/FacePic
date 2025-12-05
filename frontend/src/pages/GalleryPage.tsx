import Gallery from '../components/Gallery';

export default function GalleryPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Photo Gallery</h1>
        <p className="text-slate-600">
          All your uploaded photos in one place.
        </p>
      </div>

      <Gallery />
    </div>
  );
}
