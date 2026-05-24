#!/usr/bin/env node
/**
 * Runtime Environment Validation Script
 * Run this before starting the application in production
 */

const requiredEnvVars = {
  REACT_APP_BACKEND_URL: {
    required: true,
    description: 'Backend API base URL',
    validation: (value) => {
      if (!value) return 'Required';
      if (!value.startsWith('http')) return 'Must start with http:// or https://';
      try {
        new URL(value);
        return null;
      } catch {
        return 'Invalid URL format';
      }
    },
  },
  REACT_APP_ORCHESTRATOR_API_URL: {
    required: true,
    description: 'Orchestrator service URL',
    validation: (value) => {
      if (!value) return 'Required';
      return null;
    },
  },
  REACT_APP_GEMINI_API_KEY: {
    required: false,
    description: 'Google Gemini API Key',
    validation: (value) => {
      if (!value) return 'Warning: Gemini features will be disabled';
      if (value.length < 20) return 'Invalid API key format';
      return null;
    },
  },
  REACT_APP_JWT_SECRET: {
    required: process.env.NODE_ENV === 'production',
    description: 'JWT signing secret',
    validation: (value) => {
      if (!value && process.env.NODE_ENV === 'production') {
        return 'Required in production';
      }
      if (value && value.length < 32) {
        return 'Should be at least 32 characters for security';
      }
      return null;
    },
  },
  REACT_APP_ENABLE_VISUAL_EDITS: {
    required: false,
    description: 'Enable visual editing features',
    validation: (value) => {
      const valid = ['true', 'false', ''];
      if (value && !valid.includes(value.toLowerCase())) {
        return 'Must be "true", "false", or empty';
      }
      return null;
    },
  },
  NODE_ENV: {
    required: true,
    description: 'Node environment',
    validation: (value) => {
      const valid = ['development', 'production', 'test'];
      if (!valid.includes(value)) {
        return `Must be one of: ${valid.join(', ')}`;
      }
      return null;
    },
  },
};

const optionalEnvVars = {
  REACT_APP_OLLAMA_URL: {
    default: 'http://localhost:11434',
    description: 'Ollama service URL',
  },
  REACT_APP_WS_URL: {
    default: '',
    description: 'WebSocket URL (falls back to backend URL)',
  },
  REACT_APP_LOG_LEVEL: {
    default: process.env.NODE_ENV === 'production' ? 'error' : 'debug',
    description: 'Logging level',
  },
  REACT_APP_VERSION: {
    default: '2.0.0',
    description: 'Application version',
  },
  REACT_APP_SENTRY_DSN: {
    default: '',
    description: 'Sentry DSN for error tracking',
  },
  REACT_APP_ANALYTICS_ID: {
    default: '',
    description: 'Google Analytics ID',
  },
  PORT: {
    default: '3000',
    description: 'Development server port',
  },
};

function validateEnvironment() {
  console.log('🔍 Validating environment variables...\n');
  
  const errors = [];
  const warnings = [];
  const validated = {};
  
  // Validate required variables
  for (const [key, config] of Object.entries(requiredEnvVars)) {
    const value = process.env[key];
    const validationResult = config.validation ? config.validation(value) : null;
    
    if (config.required && !value) {
      errors.push(`❌ ${key}: Required but not set (${config.description})`);
    } else if (validationResult) {
      if (validationResult.startsWith('Warning:')) {
        warnings.push(`⚠️  ${key}: ${validationResult}`);
      } else {
        errors.push(`❌ ${key}: ${validationResult}`);
      }
    } else if (value) {
      validated[key] = value;
      console.log(`✅ ${key}: Set (${config.description})`);
    } else {
      console.log(`⚪ ${key}: Not set (optional)`);
    }
  }
  
  // Set defaults for optional variables
  for (const [key, config] of Object.entries(optionalEnvVars)) {
    if (!process.env[key] && config.default !== undefined) {
      process.env[key] = config.default;
      console.log(`⚙️  ${key}: Set to default "${config.default}" (${config.description})`);
    } else if (process.env[key]) {
      console.log(`✅ ${key}: Set (${config.description})`);
    }
  }
  
  console.log('\n📊 Environment Summary:');
  console.log(`   Mode: ${process.env.NODE_ENV || 'development'}`);
  console.log(`   Backend: ${process.env.REACT_APP_BACKEND_URL || 'Not set'}`);
  console.log(`   Version: ${process.env.REACT_APP_VERSION || 'Unknown'}`);
  
  if (errors.length > 0) {
    console.error('\n❌ Validation failed:');
    errors.forEach(error => console.error(`   ${error}`));
    console.error('\n💡 Fix these issues before starting the application.');
    process.exit(1);
  }
  
  if (warnings.length > 0) {
    console.warn('\n⚠️  Warnings:');
    warnings.forEach(warning => console.warn(`   ${warning}`));
  }
  
  if (errors.length === 0 && warnings.length === 0) {
    console.log('\n🎉 All environment variables validated successfully!');
  }
  
  // Generate .env.example if missing
  generateEnvExample();
  
  return validated;
}

function generateEnvExample() {
  const exampleContent = `# HiRo Frontend Environment Variables
# Copy this file to .env.local and fill in the values

# Required Variables
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_ORCHESTRATOR_API_URL=http://localhost:8002
REACT_APP_GEMINI_API_KEY=your_gemini_api_key_here
REACT_APP_JWT_SECRET=your_secure_jwt_secret_min_32_chars
REACT_APP_ENABLE_VISUAL_EDITS=true

# Optional Variables
REACT_APP_OLLAMA_URL=http://localhost:11434
REACT_APP_WS_URL=ws://localhost:8001
REACT_APP_LOG_LEVEL=debug
REACT_APP_VERSION=2.0.0
REACT_APP_SENTRY_DSN=
REACT_APP_ANALYTICS_ID=
PORT=3000
NODE_ENV=development

# Development Overrides (create .env.development.local)
# REACT_APP_BACKEND_URL=http://localhost:3001

# Production Overrides (create .env.production.local)
# REACT_APP_BACKEND_URL=https://api.yourdomain.com
`;

  const fs = require('fs');
  const path = require('path');
  const examplePath = path.join(process.cwd(), '.env.example');
  
  if (!fs.existsSync(examplePath)) {
    fs.writeFileSync(examplePath, exampleContent);
    console.log('\n📄 Created .env.example file with template');
  }
}

// Run validation
if (require.main === module) {
  validateEnvironment();
} else {
  module.exports = validateEnvironment;
}
