pragma solidity 0.5.16;
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/ownership/Ownable.sol';
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/math/SafeMath.sol';
import 'OpenZeppelin/openzeppelin-contracts@2.3.0/contracts/utils/ReentrancyGuard.sol';
import './interfaces/IMdexFactory.sol';
import './interfaces/IMdexPair.sol';
import 'Uniswap/uniswap-v2-core@1.0.1/contracts/libraries/Math.sol';
import './mdex/IMdexRouter.sol';
import './SafeToken.sol';
import './Strategy.sol';

contract StrategyAllHTOnly is Ownable, ReentrancyGuard, Strategy {
  using SafeToken for address;
  using SafeMath for uint;

  IMdexFactory public factory;
  IMdexRouter public router;
  address public wht;

  mapping(address => bool) public whitelistedTokens;

  /// @dev Create a new add BNB only strategy instance.
  /// @param _router The Uniswap router smart contract.
  constructor(IMdexRouter _router) public {
    factory = IMdexFactory(_router.factory());
    router = _router;
    wht = _router.WHT();
  }

  /// @dev Set whitelist tokens
  /// @param tokens Token list to set statuses
  /// @param statuses Status list to set tokens to
  function setWhitelistTokens(address[] calldata tokens, bool[] calldata statuses)
    external
    onlyOwner
  {
    require(tokens.length == statuses.length, 'tokens & statuses length mismatched');
    for (uint idx = 0; idx < tokens.length; idx++) {
      whitelistedTokens[tokens[idx]] = statuses[idx];
    }
  }

  /// @dev Execute worker strategy. Take BNB. Return LP tokens.
  /// @param data Extra calldata information passed along to this strategy.
  function execute(
    address, /* user */
    uint, /* debt */
    bytes calldata data
  ) external payable nonReentrant {
    // 1. Find out what farming token we are dealing with and min additional LP tokens.
    (address fToken, uint minLPAmount) = abi.decode(data, (address, uint));
    require(whitelistedTokens[fToken], 'token not whitelisted');
    IMdexPair lpToken = IMdexPair(factory.getPair(fToken, wht));
    // 2. Compute the optimal amount of BNB to be converted to farming tokens.
    uint balance = address(this).balance;
    (uint r0, uint r1, ) = lpToken.getReserves();
    uint rIn = lpToken.token0() == wht ? r0 : r1;
    uint aIn =
      Math.sqrt(rIn.mul(balance.mul(3992000).add(rIn.mul(3992004)))).sub(rIn.mul(1998)) / 1996;
    // 3. Convert that portion of BNB to farming tokens.
    address[] memory path = new address[](2);
    path[0] = wht;
    path[1] = fToken;
    router.swapExactETHForTokens.value(aIn)(0, path, address(this), now);
    // 4. Mint more LP tokens and return all LP tokens to the sender.
    fToken.safeApprove(address(router), 0);
    fToken.safeApprove(address(router), uint(-1));
    (, , uint moreLPAmount) =
      router.addLiquidityETH.value(address(this).balance)(
        fToken,
        fToken.myBalance(),
        0,
        0,
        address(this),
        now
      );
    require(moreLPAmount >= minLPAmount, 'insufficient LP tokens received');
    lpToken.transfer(msg.sender, lpToken.balanceOf(address(this)));
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
