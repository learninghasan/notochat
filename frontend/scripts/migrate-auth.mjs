import {getMigrations} from 'better-auth/db/migration';
import {getAuth} from '../lib/auth.mjs';
const auth=await getAuth();
const migration=await getMigrations(auth.options);
await migration.runMigrations();
console.log('NotoChat account and organization schema migrated.');
process.exit(0);
