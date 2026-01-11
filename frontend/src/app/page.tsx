'use client'

import { useEffect, useState } from 'react'
import { createBrowserClient } from '@supabase/ssr'
import { BookOpen, Tag, Bell, AlertCircle, CheckCircle2, XCircle } from 'lucide-react'

interface Course {
  id: string
  name: string
  section?: string
  description?: string
  enabled: boolean
  course_code?: string
  calendar_name?: string
  sync_without_categories: boolean
}

interface Category {
  id: string
  course_id: string
  name: string
  enabled: boolean
}

export default function Page() {
  const [courses, setCourses] = useState<Course[]>([])
  const [categories, setCategories] = useState<Record<string, Category[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      setError(null)

      const { data: coursesData, error: coursesError } = await supabase
        .from('courses')
        .select('*')
        .order('name')

      if (coursesError) throw coursesError
      setCourses(coursesData || [])

      const { data: categoriesData, error: categoriesError } = await supabase
        .from('categories')
        .select('*')
        .order('name')

      if (categoriesError) throw categoriesError

      const grouped: Record<string, Category[]> = {}
      categoriesData?.forEach((cat) => {
        if (!grouped[cat.course_id]) grouped[cat.course_id] = []
        grouped[cat.course_id].push(cat)
      })

      setCategories(grouped)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function toggleCourse(courseId: string, enabled: boolean) {
    try {
      const { error } = await supabase
        .from('courses')
        .update({ enabled })
        .eq('id', courseId)

      if (error) throw error

      setCourses(courses.map(c =>
        c.id === courseId ? { ...c, enabled } : c
      ))
    } catch (err) {
      alert(`Failed to update course: ${(err as Error).message}`)
    }
  }

  async function updateCourseField(courseId: string, field: string, value: any) {
    try {
      const { error } = await supabase
        .from('courses')
        .update({ [field]: value })
        .eq('id', courseId)

      if (error) throw error

      setCourses(courses.map(c =>
        c.id === courseId ? { ...c, [field]: value } : c
      ))
    } catch (err) {
      alert(`Failed to update ${field}: ${(err as Error).message}`)
    }
  }

  async function toggleCategory(categoryId: string, courseId: string, enabled: boolean) {
    try {
      const { error } = await supabase
        .from('categories')
        .update({ enabled })
        .eq('id', categoryId)

      if (error) throw error

      setCategories({
        ...categories,
        [courseId]: categories[courseId].map(cat =>
          cat.id === categoryId ? { ...cat, enabled } : cat
        )
      })
    } catch (err) {
      alert(`Failed to update category: ${(err as Error).message}`)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading configuration...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2 text-center">
            Connection Error
          </h2>
          <p className="text-gray-600 text-center mb-4">{error}</p>
          <button
            onClick={loadData}
            className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-6 flex items-center gap-3">
          <Bell className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Google Classroom Sync
            </h1>
            <p className="text-sm text-gray-600">
              Configure which courses and categories generate calendar events
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {courses.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <BookOpen className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              No Courses Found
            </h2>
            <p className="text-gray-600">
              Run the sync workflow to fetch your Google Classroom courses.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {courses.map(course => (
              <div key={course.id} className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden hover:shadow-md transition">
                {/* Course Header */}
                <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h2 className="text-lg font-bold text-gray-900">{course.name}</h2>
                      {course.description && (
                        <p className="text-sm text-gray-600 mt-1">{course.description}</p>
                      )}
                    </div>
                    <button
                      onClick={() => toggleCourse(course.id, !course.enabled)}
                      className={`ml-4 px-4 py-2 rounded-lg font-medium transition whitespace-nowrap ${
                        course.enabled
                          ? 'bg-green-100 text-green-800 hover:bg-green-200'
                          : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                      }`}
                    >
                      {course.enabled ? (
                        <span className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4" />
                          Enabled
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          <XCircle className="h-4 w-4" />
                          Disabled
                        </span>
                      )}
                    </button>
                  </div>

                  {/* Course Configuration Fields */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                    {/* Course Code */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                        Course Code
                      </label>
                      <input
                        type="text"
                        placeholder="e.g., CSL7510"
                        value={course.course_code || ''}
                        onChange={(e) => updateCourseField(course.id, 'course_code', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-500 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                      />
                      <p className="text-xs text-gray-500 mt-1">Used in event titles</p>
                    </div>

                    {/* Calendar Name */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                        Calendar Name
                      </label>
                      <input
                        type="text"
                        placeholder="e.g., VCC"
                        value={course.calendar_name || ''}
                        onChange={(e) => updateCourseField(course.id, 'calendar_name', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 placeholder-gray-500 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                      />
                      <p className="text-xs text-gray-500 mt-1">Display name for calendar</p>
                    </div>

                    {/* Sync Without Categories */}
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
                        Sync Mode
                      </label>
                      <button
                        onClick={() => updateCourseField(course.id, 'sync_without_categories', !course.sync_without_categories)}
                        className={`w-full px-3 py-2 rounded-md text-sm font-medium transition ${
                          course.sync_without_categories
                            ? 'bg-blue-100 text-blue-900 hover:bg-blue-200 border border-blue-300'
                            : 'bg-gray-100 text-gray-900 hover:bg-gray-200 border border-gray-300'
                        }`}
                      >
                        {course.sync_without_categories ? '✓ All Assignments' : 'Categories Only'}
                      </button>
                      <p className="text-xs text-gray-500 mt-1">
                        {course.sync_without_categories ? 'Syncing all assignments' : 'Syncing selected topics'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Categories */}
                {categories[course.id] && categories[course.id].length > 0 && (
                  <div className="p-6 bg-gray-50 border-t border-gray-200">
                    <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      Topics ({categories[course.id].filter(c => c.enabled).length}/{categories[course.id].length})
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {categories[course.id].map(category => (
                        <button
                          key={category.id}
                          onClick={() => toggleCategory(category.id, course.id, !category.enabled)}
                          className={`p-3 rounded-md text-left text-sm font-medium transition border ${
                            category.enabled
                              ? 'bg-blue-50 text-blue-900 border-blue-300 hover:bg-blue-100'
                              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            {category.enabled ? (
                              <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-blue-600" />
                            ) : (
                              <div className="h-4 w-4 border border-gray-400 rounded flex-shrink-0" />
                            )}
                            <span>{category.name}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">
            ℹ️ How It Works
          </h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Enable courses to start monitoring assignments</li>
            <li>• Set course code and calendar name for event titles</li>
            <li>• Toggle "All Assignments" to sync everything or specific topics only</li>
            <li>• Sync runs automatically at 12 PM, 6 PM, and 10 PM IST</li>
            <li>• Changes apply on the next sync</li>
          </ul>
        </div>
      </main>
    </div>
  )
}