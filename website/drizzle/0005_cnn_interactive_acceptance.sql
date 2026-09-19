-- One explicitly requested site-owner acceptance case; preserves all existing rows.
-- No credential, authentication route, account role or quota setting is modified.
INSERT INTO jobs (id,user_id,request_key,title,brief,pages,style,language,attachments,status,created_at,updated_at)
VALUES ('db69fb9d-5d27-4fc2-9553-a722e2a5acbc', (SELECT user_id FROM jobs WHERE id='2d8c4072-7aee-4f55-8fb0-8f074de4f8cb' AND title='介绍cnn'), '888b404f-51c2-4824-a334-adf048d0f6c1', '介绍cnn — Interactive CNN from First Principles', 'Create an English teaching presentation titled **CNNs from First Principles:
See It, Derive It, Build It**. Assume I know a basic neuron, forward propagation,
loss and backpropagation. Teach why a CNN is constructed this way, the meaning of
every new symbol and dimension, and how to build and train my own small CNN.

Use exactly 20 native slides. Keep titles, essential definitions, context,
equations and the main conclusion editable as native PowerPoint objects. Put
interactive experiments in bounded Content Add-in regions using this project''s
shared scene DSL and existing feature packs. Use `core`, `code` and `math`; `three`
is optional only where channel depth becomes clearer. Do not create a CNN React
application, custom execution engine, or topic-specific runtime plugin.

Each formula must define its symbols, indices, dimensions and assumptions where
first used. Explain cross-correlation versus mathematical convolution; use
cross-correlation consistently in code. Do not flip a kernel in a diagram unless
explicitly contrasting the mathematical operation. For output size include
stride, padding and dilation, and say which are held fixed in an experiment.
Explain local connectivity and weight sharing before presenting parameter
savings. Explain equivariance and the limits of translation invariance; stride,
finite boundaries and pooling matter. Use an actual worked numerical image,
not an unexplained photograph with arbitrary heatmaps. References for these
conventions are [PyTorch Conv2d](https://docs.pytorch.org/docs/2.14/generated/torch.nn.Conv2d.html)
and [Stanford''s convolution notes](https://cs231n.github.io/convolutional-networks/).

Use this teaching sequence; interaction replaces repeated static demonstration
pages, not mathematical explanations:

| Slide | Teaching question and required content | Learner experiment |
| --- | --- | --- |
| 1 | What will we be able to explain and build? Show the tiny image-to-class pipeline and honest scope. | Select a vertical or horizontal synthetic bar; see the input and class label. |
| 2 | What does an image tensor contain? Explain height, width, channels, pixel range, HWC/CHW and batch dimension. | Inspect a pixel/channel; identify its array index and numerical value. |
| 3 | Why change a fully connected neuron? Derive local receptive fields and shared weights from repeated spatial patterns. | Toggle independent versus shared patch parameters; count them. |
| 4 | How does one filter produce one output? Define every term of the cross-correlation sum and bias. | Step through the 2×2 kernel fixture below; show the four products and sum. |
| 5 | How is an entire feature map formed? Keep the kernel unchanged as it scans. | Play/pause/scrub a four-patch scan; matrix, sum and active source line agree. |
| 6 | What do stride, padding and dilation change? Derive output shape with an integer example. | Change bounded integer controls; show valid patch positions and output dimensions. |
| 7 | How do RGB channels and multiple filters work? Sum across input channels, retain separate output channels. | Select an input contribution or output filter; display channel dimensions and parameter count. |
| 8 | Why add a nonlinearity? Explain ReLU and its chosen derivative at zero. | Change a preactivation through negative/positive values; compare forward and backward gates. |
| 9 | Why reduce spatial resolution? Compare max pooling and average pooling, ties and information loss. | Inspect a 2×2 window, change one value, and route a supplied upstream gradient. |
| 10 | How far can deeper units see? Derive receptive-field size and jump through conv/pool/conv. | Step through the three layers; highlight the contributing original input region. |
| 11 | How does a feature map become a decision? Compare flattening and global average pooling, then a two-class linear head. | Inspect each feature mean and its contribution to the logits. |
| 12 | What do softmax and cross-entropy measure? Derive stable softmax, negative log likelihood and logit gradients. | Edit three logits and the target class; probabilities and loss update. |
| 13 | How does a shared kernel learn? Derive dK, db and dX from an upstream gradient. | Accumulate one patch''s gradient at a time; make repeated use of each weight visible. |
| 14 | How do we know a gradient is correct? Explain centered finite differences and their limitations at ReLU kinks. | Compare an analytic derivative to a finite difference away from a kink. |
| 15 | Build the forward pass in real Python. Comment tensor shapes and index conventions. | Edit a kernel entry in Monaco and run; actual returned values drive the displayed feature map. |
| 16 | Build the backward pass in real Python. Connect each gradient line to its equation. | Step through the same fixture; source-line highlighting, explanation and accumulated dK stay synchronized. |
| 17 | Train the complete tiny CNN. Show initialization, forward, backward, SGD and evaluation without hidden helpers. | Run the full self-contained program; plot returned loss checkpoints and report real parameter changes. |
| 18 | What changes when training changes? Explain learning rate, epochs and reproducibility. | Edit epochs or learning rate and rerun; zero learning rate must preserve weights. |
| 19 | What has this toy model actually learned? Show distinct held-out images, successes and mistakes. | Inspect held-out cases and compare training versus held-out loss/accuracy. |
| 20 | Can I now explain and extend the CNN? Recap the complete chain and offer two concrete experiments. | Reset and replay an experiment; provide the complete commented source and local launch instructions. |

Keep native text readable at presentation scale. Give each experiment a question,
an input, a visible numerical consequence and a one-sentence interpretation.
Animations need pause, step/scrub and reset. Always retain legends, signs, units
and coordinate conventions. A static PDF or unsupported PowerPoint host must
still convey the worked example through its native explanation and representative
snapshot. Never leave the fallback as a blank editor or loading spinner.

Use actual Monaco `CodeEditor` components and the local Python worker. Programs
must run with the Python standard library alone: no uploads, package installation,
network requests, NumPy, PyTorch or hidden source files. Keep experiments bounded
(normally 10 seconds or less after interpreter startup). The complete program
must train convolution weights, biases and classifier parameters using manually
implemented gradients. Fixed edge filters followed by a learned linear classifier
do not satisfy “my own CNN.” Short mechanism experiments can use JavaScript,
but their results must also be produced by an actual worker run.

Retain the complete program in an editable, scrollable code view and as a local
source artifact. Use short selected excerpts on explanation slides; do not shrink
an entire program onto one slide. Fully comment the purpose of every operation,
especially shape/index transformations and gradient accumulation. Link the
backward explanation to [Stanford''s backpropagation notes](https://cs231n.github.io/optimization-2/).

Use these deterministic fixtures and expose their values for scene assertions:

1. `X=[[1,2,3],[4,5,6],[7,8,9]]`, `K=[[1,-1],[2,0]]`, bias 0,
   stride 1, no padding/dilation. Output is `[[7,9],[13,15]]`.
   With `dZ=[[1,1],[1,1]]`, expect `dK=[[12,16],[24,28]]`, `db=4`,
   `dX=[[1,0,-1],[3,2,-1],[2,2,0]]`.
2. General output size is `floor((n+2p-d(k-1)-1)/s+1)` per spatial axis.
   `n=5,k=3,p=0,d=1,s=1` gives 3; stride 2 gives 2; padding 1 and
   stride 1 gives 5. For `Cin=3,Cout=4,k=3`, including bias gives 112
   parameters; changing spatial resolution alone does not change that count.
3. For logits `[2,1,0]` and target class 0, probabilities are approximately
   `[0.6652409558,0.2447284711,0.0900305732]`, loss `0.4076059644`, and
   logit gradient `[-0.3347590442,0.2447284711,0.0900305732]`.
4. Conv3/stride1, pool2/stride2, conv3/stride1 have receptive fields
   `3,4,8` and jumps `1,2,2`, starting from receptive field/jump `1,1`.

Use the following complete-training fixture recipe so that reviewers can
reproduce the result. Explain that it is a small synthetic teaching task, not a
benchmark or a trained general-purpose image classifier:

- Images are 6×6, one channel. Class 0 is a vertical one-pixel bar and class 1
  a horizontal bar. For each pixel, add `Random(image_seed).uniform(-.04,.04)`
  in row-major order, then clamp to `[0,1]`.
- Training order is class `[0,1]`, position `[1,3]`, variation `range(4)`;
  image seed is `100*class+10*position+variation`. This is 16 images.
- Held-out order is class `[0,1]`, position `[2,4]`, variation `range(2)`;
  image seed is `1000+100*class+10*position+variation`. This is 8 distinct
  images at positions absent from training. Do not train on these images.
- Use 4 valid 3×3 filters, ReLU, the average of each 4×4 feature map, a
  4-to-2 linear classifier and stable softmax cross-entropy: 50 parameters.
- With a single `Random(7)`, initialize the 4×3×3 kernels in filter/row/column
  order with `uniform(-.2,.2)`, then 2×4 classifier weights in class/filter
  order with `uniform(-.3,.3)`. Conv biases are `.1`; classifier biases are 0.
- Use ordinary SGD, learning rate `.15`, 30 epochs, fixed data order, no
  momentum/weight decay. Compute all derivatives from the same forward pass
  before updating any parameter; use ReLU derivative 0 at nonpositive inputs.
- Expected mean training CE before training: `0.6899881579037387`.
  After 30 epochs: `0.016981174563243915`, training accuracy `1.0`.
  Held-out CE: `0.5584269862772628`, held-out accuracy `.75`. Accept numeric
  loss differences up to `1e-6`. These values were independently calculated
  from the recipe, not observed from a generated presentation.
- Record initial and periodic losses, a convolution weight before/after,
  predictions and labels. Let `EPOCHS=0` and `LEARNING_RATE=0` be runnable
  learner edits. The latter must leave all 50 parameters unchanged.

Name scene state consistently: `lesson.step`, `lesson.codeLine`,
`conv.output`, `conv.patchSum`, `backward.dK`, `backward.dX`, `backward.db`,
`softmax.probabilities`, `softmax.loss`, and `training.result`. Derive arrays from
inputs or worker results; assertions must not be satisfied by hardcoded expected
answers. Bind Monaco `highlightLines` to `lesson.codeLine` on code walkthroughs
and show the active statement plus explanation alongside it. Derive the line map
from the shipped source after final edits; line numbers alone are not a trace of
Python execution. Use a clearly labeled **guided algorithm walkthrough**.

Every attached scene needs real `testPlan` actions and nonempty assertions:
changed inputs, correct numerical output, meaningful timeline intermediate state,
and reset. Record exact actions, actual/expected numerical values, tolerances, hashes and report/capture paths; do not count DOM presence as execution proof. Deliver the
native PPTX, matching interactive sidecar workspace and portable bundle, source
programs, citations and actual host-generated reports/captures. Return the native
PPTX `path` and matching `workspace` in `delivery.json`. Never declare desktop
PowerPoint playback passed based only on browser screenshots.', 20, 'Technical teaching; clear diagrams, readable math, interactive labs', 'en', '[]', CASE WHEN (SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')) < 100 THEN 'queued' ELSE NULL END, CAST(strftime('%s','now') AS INTEGER) * 1000, CAST(strftime('%s','now') AS INTEGER) * 1000)
ON CONFLICT(user_id,request_key) DO NOTHING;
