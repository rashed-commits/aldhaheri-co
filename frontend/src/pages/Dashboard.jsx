import { useState, useEffect } from 'react'
import Header from '../components/Header'
import ProjectCard from '../components/ProjectCard'
import projects from '../config/projects'

export default function Dashboard() {
  const [statuses, setStatuses] = useState({})

  useEffect(() => {
    projects.forEach((project) => {
      fetch(project.healthUrl, { mode: 'cors' })
        .then((res) => {
          setStatuses((prev) => ({
            ...prev,
            [project.name]: res.ok ? 'online' : 'offline',
          }))
        })
        .catch(() => {
          setStatuses((prev) => ({
            ...prev,
            [project.name]: 'offline',
          }))
        })
    })
  }, [])

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#0F0F1A' }}>
      <Header />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
          {projects.map((project) => (
            <ProjectCard
              key={project.name}
              name={project.name}
              description={project.description}
              icon={project.icon}
              url={project.url}
              healthUrl={project.healthUrl}
              status={statuses[project.name] || 'checking'}
            />
          ))}
        </div>
      </main>
    </div>
  )
}
