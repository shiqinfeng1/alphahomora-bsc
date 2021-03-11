pragma solidity 0.5.16;
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/ownership/Ownable.sol';
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/utils/ReentrancyGuard.sol';
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/math/SafeMath.sol';
import 'Uniswap/uniswap-v2-core@1.0.1/contracts/interfaces/IUniswapV2Factory.sol';
import 'Uniswap/uniswap-v2-core@1.0.1/contracts/interfaces/IUniswapV2Pair.sol';
import './uniswap/IUniswapV2Router02.sol';
import './SafeToken.sol';
import './Strategy.sol';

contract StrategyWithdrawMinimizeTrading is Ownable, ReentrancyGuard, Strategy {
  using SafeToken for address;
  using SafeMath for uint;

  IUniswapV2Factory public factory;
  IUniswapV2Router02 public router;
  address public wbnb;
  address public fToken;

  /// @dev Create a new withdraw minimize trading strategy instance.
  /// @param _router The Uniswap router smart contract.
  constructor(IUniswapV2Router02 _router, address _fToken) public {
    factory = IUniswapV2Factory(_router.factory());
    router = _router;
    wbnb = _router.WETH();
    fToken = _fToken;
  }

  /// @dev Execute worker strategy. Take LP tokens. Return fToken + BNB.
  /// @param user User address to withdraw liquidity.
  /// @param debt Debt amount in WAD of the user.
  /// @param data Extra calldata information passed along to this strategy.
  function execute(
    address user,
    uint debt,
    bytes calldata data
  ) external payable nonReentrant {
    // 1. Find out what farming token we are dealing with.
    (address _fToken, uint minFToken) = abi.decode(data, (address, uint));
    require(_fToken == fToken, 'token mismatched');
    IUniswapV2Pair lpToken = IUniswapV2Pair(factory.getPair(fToken, wbnb));
    // 2. Remove all liquidity back to BNB and farming tokens.
    lpToken.approve(address(router), uint(-1));
    router.removeLiquidityETH(fToken, lpToken.balanceOf(address(this)), 0, 0, address(this), now);
    // 3. Convert farming tokens to BNB.
    address[] memory path = new address[](2);
    path[0] = fToken;
    path[1] = wbnb;
    fToken.safeApprove(address(router), 0);
    fToken.safeApprove(address(router), uint(-1));
    uint balance = address(this).balance;
    if (debt > balance) {
      // Convert some farming tokens to BNB.
      uint remainingDebt = debt.sub(balance);
      router.swapTokensForExactETH(remainingDebt, fToken.myBalance(), path, address(this), now);
    }
    // 4. Return BNB back to the original caller.
    uint remainingBalance = address(this).balance;
    SafeToken.safeTransferBNB(msg.sender, remainingBalance);
    // 5. Return remaining farming tokens to user.
    uint remainingFToken = fToken.myBalance();
    require(remainingFToken >= minFToken, 'insufficient farming tokens received');
    if (remainingFToken > 0) {
      fToken.safeTransfer(user, remainingFToken);
    }
  }

  /// @dev Recover ERC20 tokens that were accidentally sent to this smart contract.
  /// @param token The token contract. Can be anything. This contract should not hold ERC20 tokens.
  /// @param to The address to send the tokens to.
  /// @param value The number of tokens to transfer to `to`.
  function recover(
    address token,
    address to,
    uint value
  ) external onlyOwner nonReentrant {
    token.safeTransfer(to, value);
  }

  function() external payable {}
}
