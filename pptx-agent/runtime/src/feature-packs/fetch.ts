/** Read before allocation crosses the declared limit, including chunked responses. */
export async function readBounded(response:Response,maximum:number){
 if(!response.ok)throw new Error(`Resource unavailable: HTTP ${response.status}`);if(Number(response.headers.get('content-length')??0)>maximum)throw new Error(`Resource exceeds ${maximum} bytes`);
 const reader=response.body?.getReader();if(!reader){const buffer=await response.arrayBuffer();if(buffer.byteLength>maximum)throw new Error(`Resource exceeds ${maximum} bytes`);return buffer;}
 const chunks:Uint8Array[]=[];let size=0;try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>maximum){await reader.cancel();throw new Error(`Resource exceeds ${maximum} bytes`);}chunks.push(value);}}finally{reader.releaseLock();}
 const output=new Uint8Array(size);let offset=0;for(const chunk of chunks){output.set(chunk,offset);offset+=chunk.byteLength;}return output.buffer;
}
