/** Damped height-field water and interruptible spring motion. No DOM dependencies. */
export const clamp=(value:number,min:number,max:number)=>Math.max(min,Math.min(max,value));
export class WaterField{
 readonly height:Float32Array;readonly velocity:Float32Array;private next:Float32Array;readonly pixels:Uint8Array;
 constructor(readonly width=160,readonly depth=96){this.height=new Float32Array(width*depth);this.velocity=new Float32Array(width*depth);this.next=new Float32Array(width*depth);this.pixels=new Uint8Array(width*depth*4);}
 disturb(x:number,y:number,power=.7,radius=.025){if(![x,y,power,radius].every(Number.isFinite))return;x=clamp(x,0,1);y=clamp(y,0,1);radius=clamp(radius,.008,.2);power=clamp(power,-2,2);const rx=radius*this.width,ry=radius*this.depth;const cx=x*(this.width-1),cy=y*(this.depth-1);for(let j=Math.max(1,Math.floor(cy-ry*3));j<Math.min(this.depth-1,cy+ry*3);j++)for(let i=Math.max(1,Math.floor(cx-rx*3));i<Math.min(this.width-1,cx+rx*3);i++){const d=((i-cx)/rx)**2+((j-cy)/ry)**2;const k=j*this.width+i;this.velocity[k]=clamp(this.velocity[k]+power*Math.exp(-d*1.7),-2,2);}}
 surge(direction:number){const from=direction>=0?.08:.92;for(let j=0;j<11;j++)this.disturb(from,.12+j*.075,.7*Math.sin((j+1)/12*Math.PI),.045);}
 step(){const {width:w,depth:d,height:h,velocity:v,next:n}=this;for(let y=1;y<d-1;y++)for(let x=1;x<w-1;x++){const i=y*w+x;const lap=h[i-1]+h[i+1]+h[i-w]+h[i+w]-4*h[i];const edge=Math.min(x,y,w-1-x,d-1-y);v[i]=clamp((v[i]+lap*.24)*(edge<8?.9+.011*edge:.986),-2.5,2.5);n[i]=clamp((h[i]+v[i])*.999,-3,3);}h.set(n);}
 sample(x:number,y:number){x=clamp(x,0,1)*(this.width-1);y=clamp(y,0,1)*(this.depth-1);const ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy;const a=this.height[iy*this.width+ix],b=this.height[iy*this.width+Math.min(ix+1,this.width-1)],c=this.height[Math.min(iy+1,this.depth-1)*this.width+ix],d=this.height[Math.min(iy+1,this.depth-1)*this.width+Math.min(ix+1,this.width-1)];return (a+(b-a)*fx)*(1-fy)+(c+(d-c)*fx)*fy;}
 encode(){for(let i=0;i<this.height.length;i++){const value=Math.round((clamp(this.height[i],-3,3)/6+.5)*65535);const p=i*4;this.pixels[p]=value>>8;this.pixels[p+1]=value&255;this.pixels[p+2]=Math.round(clamp(Math.abs(this.velocity[i])*.65,0,1)*255);this.pixels[p+3]=255;}return this.pixels;}
 energy(){let total=0;for(let i=0;i<this.height.length;i++)total+=this.height[i]**2+this.velocity[i]**2;return total;}
}
export type Spring={value:number;velocity:number};
export function advanceSpring(s:Spring,target:number,dt:number,stiffness=90,damping=18){dt=clamp(dt,0,1/30);s.velocity+=(target-s.value)*stiffness*dt;s.velocity*=Math.exp(-damping*dt);s.value+=s.velocity*dt;return s.value;}
export type CardPose={x:number;y:number;scale:number;roll:number;pitch:number;alpha:number};
export function cardTarget(index:number,active:number,total:number,cardWidth:number):CardPose{const next=(active+1)%total,previous=(active+total-1)%total;if(index===active)return {x:0,y:0,scale:1,roll:0,pitch:0,alpha:1};if(index===previous)return {x:-cardWidth*.64,y:30,scale:.77,roll:-7,pitch:7,alpha:.75};if(index===next)return {x:cardWidth*.64,y:30,scale:.77,roll:7,pitch:7,alpha:.75};return {x:0,y:110,scale:.64,roll:0,pitch:15,alpha:0};}
export function switchDirection(from:number,to:number,total:number){const forward=(to-from+total)%total,backward=(from-to+total)%total;return forward<=backward?1:-1;}
