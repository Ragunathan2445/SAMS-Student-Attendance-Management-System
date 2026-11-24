import { Link } from "react-router-dom";
import { SchoolMark } from "../components/SchoolMark";

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-white px-4 text-center">
      <div>
        <SchoolMark size={56} className="mx-auto" />
        <h1 className="mt-6 text-3xl font-semibold">Page not found</h1>
        <p className="mt-2 text-ink-soft">The page you are looking for does not exist.</p>
        <Link to="/" className="mt-6 inline-block rounded-lg bg-brand-700 px-5 py-2.5 font-medium text-white hover:bg-brand-800">Back to home</Link>
      </div>
    </div>
  );
}
