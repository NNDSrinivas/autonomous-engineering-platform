// Test file for NAVI repo-aware generative repair
// This should be fixed with the project's conventions

function brokenFunction() {
  const message = "Hello world";
  console.log(message
  // Missing closing parenthesis and brace

const anotherFunction = () => {
  if (true {
    return "test"
  // Missing closing parenthesis and brace

// This should follow the repo's React patterns if detected
const MyComponent = () => {
  const [state, setState] = useState(
  // Missing closing for useState call
  
// Missing closing brace for file scope and proper React return