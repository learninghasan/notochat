function unavailable(){return Response.json({detail:'Backend is not connected. Try the interactive demo, or set BACKEND_URL in the server environment.'},{status:503});}
export const GET=unavailable;
export const POST=unavailable;
export const PATCH=unavailable;
