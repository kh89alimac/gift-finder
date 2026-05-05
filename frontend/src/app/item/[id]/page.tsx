import type { Metadata } from 'next';
import ItemDetailClient from './ItemDetailClient';

interface PageProps {
  params: { id: string };
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  return {
    title: `Gift Details`,
    description: 'View gift details, tags, and similar items.',
  };
}

export default function ItemPage({ params }: PageProps) {
  return <ItemDetailClient id={params.id} />;
}
