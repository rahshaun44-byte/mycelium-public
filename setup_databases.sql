-- ============================================================================
-- QUANTUM FLEX: Database & Schema Initialization Template
-- ============================================================================
-- NOTE: Passwords should be injected dynamically or rotated via tools/rotate_credentials.py

-- 1. Create Core Databases
CREATE DATABASE quantum_flex;
CREATE DATABASE telemetry;
CREATE DATABASE amara_matrix;

-- 2. Create Roles with appropriate privileges
-- Passwords must be overridden during deployment
CREATE ROLE quantum_sentinel WITH LOGIN PASSWORD 'SET_YOUR_SECURE_PASSWORD';
CREATE ROLE rahshaunchambers WITH LOGIN SUPERUSER PASSWORD 'SET_YOUR_SECURE_PASSWORD';
CREATE ROLE ghostnode WITH LOGIN PASSWORD 'SET_YOUR_SECURE_PASSWORD';
CREATE ROLE sentinel_service WITH LOGIN PASSWORD 'SET_YOUR_SECURE_PASSWORD';
CREATE ROLE amara_admin WITH LOGIN PASSWORD 'SET_YOUR_SECURE_PASSWORD';

-- Grant database connect privileges
GRANT CONNECT ON DATABASE quantum_flex TO quantum_sentinel;
GRANT CONNECT ON DATABASE telemetry TO sentinel_service;
GRANT CONNECT ON DATABASE telemetry TO ghostnode;
GRANT CONNECT ON DATABASE amara_matrix TO amara_admin;
