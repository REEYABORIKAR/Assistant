import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const Projects = () => {
  const { user, loading: authLoading } = useAuth();
  const { tenant, loading: tenantLoading } = useTenant();
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedProject, setSelectedProject] = useState(null);

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectType, setProjectType] = useState('Enterprise ERP & Cloud Migration');
  const [userRole, setUserRole] = useState('Product Manager');
  const [projectDescription, setProjectDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [user, tenant]);

  const fetchProjects = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/api/v1/projects');
      const list = Array.isArray(response.data) ? response.data : (response.data?.projects || response.data?.items || []);
      if (list.length > 0) {
        setProjects(list);
        setSelectedProject(list[0]);
      } else {
        setProjects([]);
        setSelectedProject(null);
      }
    } catch (err) {
      setProjects([]);
      setSelectedProject(null);
      setError("Couldn't load projects. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || tenantLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-cyan-400 font-medium">Loading projects...</div>;
  }

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  const handleStartProjectChat = async (project) => {
    try {
      const projName = project?.name || 'New Project';
      const response = await api.post('/api/v1/conversations', {
        title: `${projName} Chat`,
        project_id: project?.id,
        initial_message: `🚀 **Project Workspace Connected:** \`${projName}\`\n\n**Scope:** ${project?.description || 'Enterprise Requirement Gathering'}\n\nHow would you like REFYNE AI to assist with your requirements today?`
      });
      const convId = response.data?.id;
      if (convId) {
        navigate(`/chat?session=${convId}`);
      } else {
        navigate('/chat');
      }
    } catch (err) {
      console.error('Error starting project chat', err);
      navigate('/chat');
    }
  };

  const handleCreateProjectSubmit = async (e) => {
    e.preventDefault();
    if (!projectName.trim() || submitting) return;

    setSubmitting(true);
    setError('');

    try {
      // 1. Create project via backend API
      const projRes = await api.post('/api/v1/projects', {
        name: projectName.trim(),
        description: projectDescription.trim() || `${projectType} application requirements for ${userRole}`
      });

      const createdProject = projRes.data;

      // 2. Automatically create dedicated chat session named with the project title
      const convRes = await api.post('/api/v1/conversations', {
        title: `${projectName.trim()} Chat`,
        project_id: createdProject?.id,
        role: userRole,
        project_type: projectType
      });

      const convId = convRes.data?.id;

      setShowCreateModal(false);
      setProjectName('');
      setProjectDescription('');

      // 3. Immediately jump to chat with the new project chat session
      if (convId) {
        navigate(`/chat?session=${convId}`);
      } else {
        navigate('/chat');
      }
    } catch (err) {
      console.error('Failed to create project', err);
      setError('Failed to create project. Created local chat session instead.');
      // Fallback: create chat directly with project name
      try {
        const fallbackConv = await api.post('/api/v1/conversations', {
          title: `${projectName.trim()} Chat`,
          role: userRole,
          project_type: projectType
        });
        setShowCreateModal(false);
        navigate(`/chat?session=${fallbackConv.data.id}`);
      } catch (fallbackErr) {
        setShowCreateModal(false);
        navigate('/chat');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const safeProjects = Array.isArray(projects) ? projects : [];

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy relative">
      {/* Create Project Modal Dialog */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.2)] animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-2">
                <span className="text-2xl">✨</span>
                <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                  Create New Project Workspace
                </h3>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-rose-400 font-bold text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateProjectSubmit} className="space-y-4">
              {/* Project Name */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Project Name <span className="text-cyan-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="e.g. Enterprise ERP Modernization"
                  className="glass-input w-full py-2.5 px-3 text-sm"
                />
              </div>

              {/* Project Type / Industry */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Project Type / Industry
                </label>
                <select
                  value={projectType}
                  onChange={(e) => setProjectType(e.target.value)}
                  className="glass-input w-full py-2.5 px-3 text-sm bg-slate-900 text-slate-200 border-slate-700"
                >
                  <option value="Enterprise ERP & Cloud Migration">Enterprise ERP & Cloud Migration</option>
                  <option value="Fintech & Banking Platform">Fintech & Banking Platform</option>
                  <option value="Healthcare & HIPAA Compliance">Healthcare & HIPAA Compliance</option>
                  <option value="E-Commerce & Digital Portal">E-Commerce & Digital Portal</option>
                  <option value="Cybersecurity & Risk Management">Cybersecurity & Risk Management</option>
                  <option value="Custom AI Platform">Custom AI Platform</option>
                </select>
              </div>

              {/* Your Role */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Your Role
                </label>
                <select
                  value={userRole}
                  onChange={(e) => setUserRole(e.target.value)}
                  className="glass-input w-full py-2.5 px-3 text-sm bg-slate-900 text-slate-200 border-slate-700"
                >
                  <option value="Product Manager">Product Manager</option>
                  <option value="Business Analyst">Business Analyst</option>
                  <option value="Lead Software Architect">Lead Software Architect</option>
                  <option value="Engineering Manager">Engineering Manager</option>
                  <option value="QA & Compliance Lead">QA & Compliance Lead</option>
                </select>
              </div>

              {/* Project Description */}
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                  Project Description / Objective
                </label>
                <textarea
                  rows={3}
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Migration of core monolithic ERP services to microservices AI workflow architecture..."
                  className="glass-input w-full p-3 text-xs"
                />
              </div>

              {/* Buttons */}
              <div className="pt-3 border-t border-cyan-500/20 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="glass-button-secondary text-xs px-4 py-2.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!projectName.trim() || submitting}
                  className="glass-button text-xs px-6 py-2.5 font-bold shadow-[0_0_15px_rgba(0,240,255,0.4)]"
                >
                  {submitting ? 'Creating Project...' : '🚀 Create Project & Start Chat'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main Projects Workspace */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span>📁</span>
              <span>Project Workspaces</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">Manage tenant requirement portfolios and active workflow scopes</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="glass-button font-bold text-sm shadow-[0_0_15px_rgba(0,240,255,0.3)]"
          >
            <span>+ Create New Project</span>
          </button>
        </header>

        {error && <div className="p-4 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-sm">{error}</div>}

        {loading && <div className="text-center py-12 text-cyan-400 font-medium">Loading active projects...</div>}

        {!loading && safeProjects.length === 0 && (
          <div className="glass-card p-12 text-center text-slate-400 space-y-4">
            <p className="text-lg font-bold text-slate-200">No projects yet</p>
            <p className="text-sm text-slate-400">Create your first project to get started</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="glass-button mx-auto font-bold shadow-[0_0_15px_rgba(0,240,255,0.3)]"
            >
              + Create New Project
            </button>
          </div>
        )}

        {!loading && safeProjects.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {safeProjects.map((project) => (
              <div
                key={project.id}
                onClick={() => setSelectedProject(project)}
                className={`glass-card p-6 flex flex-col justify-between space-y-4 transition-all duration-200 cursor-pointer ${
                  selectedProject?.id === project.id ? 'border-cyan-400/80 shadow-[0_0_20px_rgba(0,240,255,0.2)] bg-slate-900/80' : 'hover:border-cyan-500/40'
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="badge-glow-cyan text-[10px]">{project.status || 'ACTIVE'}</span>
                    <span className="text-[11px] text-slate-400 font-mono">ID: {project.id}</span>
                  </div>
                  <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                    {project.name}
                  </h3>
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {project.description || 'No description provided.'}
                  </p>
                </div>

                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center space-x-3">
                    <span>📋 {project.requirementsCount || 0} REQs</span>
                    <span>⚠️ {project.risksCount || 0} Risks</span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleStartProjectChat(project);
                    }}
                    className="text-[11px] text-cyan-400 hover:text-cyan-200 font-bold hover:underline"
                  >
                    💬 Chat →
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Right Context Drawer Panel: Project Details */}
      <aside className="w-80 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6">
        <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
          Selected Project Details
        </h3>

        {selectedProject ? (
          <div className="space-y-6">
            <div className="glass-card p-5 space-y-3">
              <h4 className="text-base font-bold text-slate-100">{selectedProject.name}</h4>
              <p className="text-xs text-slate-300 leading-relaxed">{selectedProject.description}</p>
              <div className="pt-3 border-t border-slate-800 text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Created Date:</span>
                  <span className="text-slate-200 font-mono">{selectedProject.createdAt}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span className="badge-glow-green text-[10px]">{selectedProject.status || 'ACTIVE'}</span>
                </div>
              </div>
            </div>

            <div className="glass-card p-5 space-y-3">
              <h5 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Quick Actions</h5>
              <div className="space-y-2">
                <button
                  onClick={() => handleStartProjectChat(selectedProject)}
                  className="w-full glass-button text-xs py-2.5 font-bold shadow-[0_0_12px_rgba(0,240,255,0.3)]"
                >
                  💬 Start Project Chat
                </button>
                <button
                  onClick={() => navigate(`/documents`)}
                  className="w-full glass-button-secondary text-xs py-2"
                >
                  📄 View Documents
                </button>
                <button
                  onClick={() => navigate(`/workflows`)}
                  className="w-full glass-button-secondary text-xs py-2"
                >
                  ⚡ Run Workflow
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-400 text-center py-8">Select a project to inspect details.</div>
        )}
      </aside>
    </div>
  );
};

export default Projects;