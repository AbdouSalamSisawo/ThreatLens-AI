import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";

export function NotFoundPage() {
  return (
    <Layout>
      <div className="mx-auto flex max-w-6xl flex-col items-center px-4 py-24 text-center">
        <p className="font-mono text-5xl font-semibold text-accent">404</p>
        <h1 className="mt-4 text-xl font-semibold text-text">Page not found</h1>
        <p className="mt-2 max-w-sm text-sm text-text-dim">
          The page you requested does not exist in this application.
        </p>
        <Link
          to="/"
          className="mt-6 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
        >
          Back to home
        </Link>
      </div>
    </Layout>
  );
}
