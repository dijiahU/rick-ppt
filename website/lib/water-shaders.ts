export const WATER_VERTEX=`
attribute vec2 aPosition;
varying vec2 vUv;
void main(){vUv=aPosition*.5+.5;gl_Position=vec4(aPosition,0.,1.);}
`;
export const WATER_FRAGMENT=`
precision highp float;
varying vec2 vUv;
uniform vec2 uResolution;
uniform vec2 uTexel;
uniform float uTime;
uniform sampler2D uHeight;
uniform sampler2D uEnvironment;
uniform vec4 uCards[6];
uniform vec2 uLamp;
uniform vec3 uPointer;
const float PI=3.14159265;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);}
float readHeight(vec2 p){vec2 rg=texture2D(uHeight,clamp(p,.001,.999)).rg;return ((rg.x*256.+rg.y)/257.-.5)*6.;}
// One travelling swell with aligned harmonics: soft parallel crests, no crossing lattice.
float swellPhase(vec2 p){return p.y*6.4+sin(p.x*1.05+uTime*.05)*.55+sin(p.x*2.8-uTime*.08)*.18-uTime*.88;}
float smallWaves(vec2 p){float phase=swellPhase(p);float amplitude=.82+.18*noise(vec2(p.x*1.4,p.y*.3));return (sin(phase)*.055+sin(phase*2.+.35)*.009+sin(phase*3.+sin(p.x*2.)*.4)*.0035)*amplitude;}
// Approximate sunlight focusing from the curvature of smooth travelling waves.
// The ray-map Jacobian produces continuous curved folds rather than cell borders.
float poolCaustics(vec2 p){
 float t=uTime*.44;
 vec2 k0=vec2(2.8,1.2),k1=vec2(-1.6,3.1),k2=vec2(3.6,-2.3),k3=vec2(.7,4.5);
 float h0=-.095*sin(dot(p,k0)-t);
 float h1=-.075*sin(dot(p,k1)+t*.83+1.9);
 float h2=-.034*sin(dot(p,k2)-t*1.17+3.7);
 float h3=-.021*sin(dot(p,k3)+t*.67+.8);
 float xx=h0*k0.x*k0.x+h1*k1.x*k1.x+h2*k2.x*k2.x+h3*k3.x*k3.x;
 float yy=h0*k0.y*k0.y+h1*k1.y*k1.y+h2*k2.y*k2.y+h3*k3.y*k3.y;
 float xy=h0*k0.x*k0.y+h1*k1.x*k1.y+h2*k2.x*k2.y+h3*k3.x*k3.y;
 float determinant=(1.+xx*1.25)*(1.+yy*1.25)-xy*xy*1.5625;
 float focus=exp(-determinant*determinant*36.);
 float glow=exp(-abs(determinant)*2.1);
 float concentration=.65+.35*noise(p*1.7+vec2(t*.16,-t*.09));
 return (focus*.74+glow*.26)*concentration;
}
vec3 environment(vec3 ray){vec2 e=vec2(atan(ray.z,ray.x)/(2.*PI)+.5,acos(clamp(ray.y,-1.,1.))/PI);e.y=min(e.y,.38);return texture2D(uEnvironment,e).rgb;}
void main(){
 vec2 uv=vUv;vec2 topUv=vec2(uv.x,1.-uv.y);float aspect=uResolution.x/uResolution.y;
 // A shallow perspective plane. The simulated field remains in screen coordinates
 // so a pointer disturbance and its floating paper share the same place.
 float perspective=1./(.55+topUv.y*1.15);
 vec2 p=vec2((uv.x-.5)*aspect*4.,3.2)*perspective;
 p*=max(1.,1.2/aspect);
 float h=readHeight(topUv);float dx=(readHeight(topUv+vec2(uTexel.x,0))-readHeight(topUv-vec2(uTexel.x,0)))*.9;
 float dy=(readHeight(topUv+vec2(0,uTexel.y))-readHeight(topUv-vec2(0,uTexel.y)))*.9;
 float e=.035;dx+=(smallWaves(p+vec2(e,0))-smallWaves(p-vec2(e,0)))/(2.*e)*.42;dy+=(smallWaves(p+vec2(0,e))-smallWaves(p-vec2(0,e)))/(2.*e)*.42;
 vec3 normal=normalize(vec3(-dx*1.25,1.,dy*1.25));vec3 view=normalize(vec3((.5-uv.x)*.4,.86,.82+uv.y*.32));vec3 reflected=reflect(-view,normal);
 float fresnel=.025+.975*pow(1.-max(0.,dot(view,normal)),5.);
 vec2 refracted=p+normal.xz*.28;
 // A shallow bath of diluted developer under a red safelight: pale coral where the lamp reaches, deeper rose away from it.
 vec2 lampDelta=(topUv-uLamp)*vec2(aspect,1.);float lampDistance=dot(lampDelta,lampDelta);
 float lampPool=exp(-lampDistance*1.05),lampCore=exp(-lampDistance*9.);
 vec2 pointerDelta=(topUv-uPointer.xy)*vec2(aspect,1.);float torch=uPointer.z*exp(-dot(pointerDelta,pointerDelta)*11.);
 float light=.5+lampPool*.52+lampCore*.3+torch*.3;
 vec3 safelight=vec3(.96,.24,.14),bath=vec3(.97,.56,.47);
 // Clear water: the tray floor is seen plainly through it, with no grain or cloudiness of its own. What shows the
 // water is light: bright caustic lines focused on the floor by the waves, and the lamp glinting on the surface.
 vec3 floorColor=vec3(.31,.13,.11)+bath*light*(.5+smallWaves(p)*.2+clamp(h,-.3,.3)*.06);
 float bathLight=poolCaustics(refracted*2.1+vec2(.7,1.4));
 floorColor+=vec3(1.,.8,.7)*pow(bathLight,1.7)*light*.15;
 // Prints shade the tray floor beneath them, offset away from the lamp.
 for(int i=0;i<6;i++){vec4 card=uCards[i];if(card.z>0.){vec2 away=normalize(card.xy-uLamp+vec2(.0001))*.012;vec2 q=abs(topUv-(card.xy+away+normal.xz*.02))-card.zw;float edge=length(max(q,0.))+min(max(q.x,q.y),0.);floorColor*=1.-.34*smoothstep(.03,-.004,edge);}}
 reflected.y=max(.04,reflected.y);
 vec3 reflection=vec3(.36,.16,.135)+bath*(lampPool*.42+torch*.3)+safelight*lampCore*.5;
 reflection+=environment(normalize(reflected))*bath*.06;
 // Little of the room is mirrored in it, so the floor is not veiled.
 vec3 water=mix(floorColor,reflection,clamp(fresnel+.03,0.,.45));
 // Broad shading describes each small wave; highlights are the lamp itself, broken by the surface.
 water*=1.+clamp(normal.x*.1+normal.z*.26,-.16,.16);
 vec3 toLamp=normalize(vec3((uLamp.x-topUv.x)*aspect,.42,(topUv.y-uLamp.y)+.2));
 float spec=pow(max(0.,dot(reflect(-toLamp,normal),view)),42.);
 float glint=pow(max(0.,dot(reflect(-toLamp,normal),view)),220.);
 water+=vec3(1.,.62,.5)*(spec*.26+glint*.4)*(.25+lampPool);
 vec3 toPointer=normalize(vec3((uPointer.x-topUv.x)*aspect,.5,(topUv.y-uPointer.y)+.05));
 water+=vec3(1.,.7,.6)*pow(max(0.,dot(reflect(-toPointer,normal),view)),60.)*torch*.45;
 water+=bath*texture2D(uHeight,topUv).b*.05*light;
 // The tray's far corners fall off a little; its lower edge meets the wall below.
 float vignette=clamp(length((uv-.5)*vec2(1.,.82)),0.,1.);water*=1.-vignette*vignette*.22;
 // The water deepens into shade over its lowest quarter, so the tray has no edge where it meets the room below.
 float rim=smoothstep(0.,.26,uv.y);water=mix(vec3(.34,.14,.12),water,rim);
 gl_FragColor=vec4(clamp(water,0.,1.),1.);
}
`;
