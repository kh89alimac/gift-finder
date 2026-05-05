'use client';

import { useState } from 'react';
import {
  useTagTypes,
  useTags,
  useCreateTagType,
  useUpdateTagType,
  useDeleteTagType,
  useCreateTag,
  useUpdateTag,
  useDeleteTag,
} from '../../../lib/hooks/admin/useTaxonomy';

export default function TaxonomyPage() {
  const { data: tagTypes, isLoading } = useTagTypes();
  const [selectedTypeId, setSelectedTypeId] = useState<string | null>(null);
  const { data: tags } = useTags(selectedTypeId ?? undefined);

  const { mutate: createTagType, isPending: isCreatingType } = useCreateTagType();
  const { mutate: updateTagType } = useUpdateTagType();
  const { mutate: deleteTagType } = useDeleteTagType();
  const { mutate: createTag, isPending: isCreatingTag } = useCreateTag();
  const { mutate: updateTag } = useUpdateTag();
  const { mutate: deleteTag } = useDeleteTag();

  const [newTypeName, setNewTypeName] = useState('');
  const [newTagName, setNewTagName] = useState('');
  const [editingTypeId, setEditingTypeId] = useState<string | null>(null);
  const [editingTypeName, setEditingTypeName] = useState('');
  const [editingTagId, setEditingTagId] = useState<string | null>(null);
  const [editingTagName, setEditingTagName] = useState('');

  const selectedType = tagTypes?.find((t) => t.id === selectedTypeId);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-warm-950">Taxonomy</h1>
        <p className="text-sm text-warm-500 mt-0.5">
          Manage tag types and tags for categorizing gifts
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-6">
        {/* Left: Tag types list */}
        <aside className="flex flex-col gap-4">
          <div className="rounded-2xl border border-warm-200 bg-white overflow-hidden">
            <div className="px-4 py-3 border-b border-warm-100 bg-warm-50">
              <h2 className="text-sm font-semibold text-warm-700">Tag Types</h2>
            </div>

            {isLoading ? (
              <div className="p-4 flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="skeleton h-9 rounded-lg" aria-hidden="true" />
                ))}
              </div>
            ) : (
              <ul className="py-1">
                {tagTypes?.map((type) => (
                  <li key={type.id}>
                    {editingTypeId === type.id ? (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          updateTagType({ id: type.id, data: { name: editingTypeName } });
                          setEditingTypeId(null);
                        }}
                        className="flex items-center gap-2 px-3 py-1.5"
                      >
                        <input
                          type="text"
                          value={editingTypeName}
                          onChange={(e) => setEditingTypeName(e.target.value)}
                          autoFocus
                          className="flex-1 rounded border border-gift-400 px-2 py-1 text-sm focus:outline-none"
                          aria-label="Edit tag type name"
                        />
                        <button type="submit" className="text-xs text-gift-600 font-medium">
                          Save
                        </button>
                        <button type="button" onClick={() => setEditingTypeId(null)} className="text-xs text-warm-400">
                          ×
                        </button>
                      </form>
                    ) : (
                      <div
                        className={`group flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors ${
                          selectedTypeId === type.id
                            ? 'bg-gift-50 border-r-2 border-gift-500'
                            : 'hover:bg-warm-50'
                        }`}
                        onClick={() => setSelectedTypeId(type.id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => e.key === 'Enter' && setSelectedTypeId(type.id)}
                        aria-pressed={selectedTypeId === type.id}
                      >
                        <span className="flex-1 text-sm font-medium text-warm-800">{type.name}</span>
                        <span className="text-xs text-warm-400">{type.tags.length}</span>
                        <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingTypeName(type.name);
                              setEditingTypeId(type.id);
                            }}
                            className="text-warm-400 hover:text-warm-600"
                            aria-label={`Edit ${type.name}`}
                          >
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (confirm(`Delete tag type "${type.name}"?`)) deleteTagType(type.id);
                            }}
                            className="text-warm-300 hover:text-blush-500"
                            aria-label={`Delete ${type.name}`}
                          >
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {/* Add new tag type */}
            <div className="border-t border-warm-100 p-3">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newTypeName.trim()) return;
                  createTagType({ name: newTypeName.trim() }, {
                    onSuccess: () => setNewTypeName(''),
                  });
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  placeholder="New type name…"
                  value={newTypeName}
                  onChange={(e) => setNewTypeName(e.target.value)}
                  className="flex-1 rounded-lg border border-warm-200 px-3 py-1.5 text-xs focus:border-gift-400 focus:outline-none"
                  aria-label="New tag type name"
                />
                <button
                  type="submit"
                  disabled={isCreatingType || !newTypeName.trim()}
                  className="rounded-lg bg-gift-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-gift-600 disabled:opacity-50"
                >
                  Add
                </button>
              </form>
            </div>
          </div>
        </aside>

        {/* Right: Tags within selected type */}
        <section>
          {!selectedType ? (
            <div className="flex flex-col items-center justify-center h-64 rounded-2xl border border-dashed border-warm-300 text-warm-400">
              <span className="text-3xl mb-2" aria-hidden="true">👈</span>
              <p className="text-sm">Select a tag type to manage its tags</p>
            </div>
          ) : (
            <div className="rounded-2xl border border-warm-200 bg-white overflow-hidden">
              <div className="px-5 py-4 border-b border-warm-100 bg-warm-50 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-warm-900">{selectedType.name}</h2>
                  <p className="text-xs text-warm-400 mt-0.5">{tags?.length ?? 0} tags</p>
                </div>
              </div>

              <div className="p-4">
                {/* Add tag form */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!newTagName.trim() || !selectedTypeId) return;
                    createTag(
                      { name: newTagName.trim(), tagTypeId: selectedTypeId },
                      { onSuccess: () => setNewTagName('') }
                    );
                  }}
                  className="flex gap-2 mb-4"
                >
                  <input
                    type="text"
                    placeholder="New tag name…"
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    className="flex-1 rounded-lg border border-warm-200 px-4 py-2 text-sm focus:border-gift-400 focus:outline-none"
                    aria-label="New tag name"
                  />
                  <button
                    type="submit"
                    disabled={isCreatingTag || !newTagName.trim()}
                    className="rounded-full bg-gift-500 px-5 py-2 text-sm font-semibold text-white hover:bg-gift-600 disabled:opacity-50"
                  >
                    Add Tag
                  </button>
                </form>

                {/* Tags list */}
                <div className="flex flex-wrap gap-2">
                  {tags?.map((tag) => (
                    <div
                      key={tag.id}
                      className="group flex items-center gap-1.5 rounded-full border border-warm-200 bg-warm-50 px-3 py-1.5"
                    >
                      {editingTagId === tag.id ? (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            updateTag({ id: tag.id, data: { name: editingTagName } });
                            setEditingTagId(null);
                          }}
                          className="flex items-center gap-1"
                        >
                          <input
                            type="text"
                            value={editingTagName}
                            onChange={(e) => setEditingTagName(e.target.value)}
                            autoFocus
                            className="w-28 rounded border border-gift-400 px-1.5 py-0.5 text-xs focus:outline-none"
                            aria-label="Edit tag name"
                          />
                          <button type="submit" className="text-xs text-gift-600 font-medium">✓</button>
                          <button type="button" onClick={() => setEditingTagId(null)} className="text-xs text-warm-400">✕</button>
                        </form>
                      ) : (
                        <>
                          <span className="text-sm text-warm-800 font-medium">{tag.name}</span>
                          {tag.itemCount !== undefined && (
                            <span className="text-xs text-warm-400">({tag.itemCount})</span>
                          )}
                          <button
                            type="button"
                            onClick={() => { setEditingTagName(tag.name); setEditingTagId(tag.id); }}
                            className="opacity-0 group-hover:opacity-100 text-warm-400 hover:text-warm-600 transition-opacity"
                            aria-label={`Edit tag ${tag.name}`}
                          >
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              if (confirm(`Delete tag "${tag.name}"?`)) deleteTag(tag.id);
                            }}
                            className="opacity-0 group-hover:opacity-100 text-warm-300 hover:text-blush-500 transition-opacity"
                            aria-label={`Delete tag ${tag.name}`}
                          >
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </>
                      )}
                    </div>
                  ))}

                  {(!tags || tags.length === 0) && (
                    <p className="text-sm text-warm-400 py-4">
                      No tags in this category yet. Add one above.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
