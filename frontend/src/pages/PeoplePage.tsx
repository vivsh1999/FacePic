import PersonList from '../components/PersonList';

export default function PeoplePage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">People</h1>
        <p className="text-slate-600">
          Click on a person to see all their photos. Click the edit icon to add a name.
        </p>
      </div>

      <PersonList />
    </div>
  );
}
