CREATE TABLE users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prompts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  content TEXT NOT NULL,
  category TEXT,
  tags TEXT,
  visibility TEXT NOT NULL DEFAULT 'team',
  status TEXT NOT NULL DEFAULT 'draft',
  created_by TEXT REFERENCES users(id),
  usage_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skills (
  id TEXT PRIMARY KEY,
  skill_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT,
  tags TEXT,
  version TEXT NOT NULL,
  author_id TEXT REFERENCES users(id),
  risk_level TEXT NOT NULL DEFAULT 'low',
  status TEXT NOT NULL DEFAULT 'draft',
  package_hash TEXT,
  install_count INTEGER NOT NULL DEFAULT 0,
  rating REAL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skill_versions (
  id TEXT PRIMARY KEY,
  skill_ref_id TEXT REFERENCES skills(id),
  version TEXT NOT NULL,
  changelog TEXT,
  package_url TEXT,
  package_hash TEXT,
  manifest TEXT,
  created_by TEXT REFERENCES users(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE skill_installs (
  id TEXT PRIMARY KEY,
  skill_ref_id TEXT REFERENCES skills(id),
  user_id TEXT REFERENCES users(id),
  version TEXT,
  target_tool TEXT,
  install_scope TEXT,
  install_path TEXT,
  status TEXT,
  installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  actor_id TEXT REFERENCES users(id),
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata TEXT,
  ip_address TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
